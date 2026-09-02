# Tasks — `night-pipeline`

## 1. The stage table, as code

- [x] 1.1 `secondshift/night/stages.py`: the six stages in schema order, each
      with its agent role and a `can_run(completed)` predicate. It must read as
      the proposal's table — that table is the specification.
- [x] 1.2 Assert the role map against `agents.roster.permitted_roles(conn)`, so
      a role renamed in the schema fails here rather than at 2am.
- [x] 1.3 Assert the stage names against the `run_stages` CHECK constraint, read
      from `sqlite_master` — the same technique `roster.permitted_roles` uses.
      A seventh stage added to the schema with no definition must fail.

## 2. Policy resolution and quarantine

- [x] 2.1 Resolve once per entry, before any run row exists.
- [x] 2.2 Where not permitted: record a typed failure, leave the entry queued,
      open nothing. Assert no `runs` row and no `model_calls` row.
- [x] 2.3 Test the concrete trap: a `local-only` entry on a `cloud` profile must
      not reach `EchoReasoner`.

## 3. The loop

- [x] 3.1 `secondshift/night/run.py`: open the run, transition the entry to
      `running`, walk the stages, close the run.
- [x] 3.2 Each stage in its own transaction — insert `running`, invoke,
      `complete_run_stage`. No enclosing transaction.
- [x] 3.3 A stage that raises is recorded `failed` with a typed failure, and the
      walk continues per the predicates.
- [x] 3.4 Outcome derived at close: `complete`, `degraded`, or `failed`.
- [x] 3.5 `close_run` on every terminal path, including the exception path.
- [x] 3.6 On failure, entry returns to `queued`.

## 4. The stages themselves

- [x] 4.1 `brief`: entry text plus `assemble_context` where retrieval is
      available; where it is not, the entry text alone **and the brief says so**.
- [x] 4.2 `research`: skipped with "no research provider is configured" until
      `research` ships. Skipped, never failed — nothing was attempted.
- [x] 4.3 `mockups`, `build`, `critique`: invoke their roles on what completed.
- [x] 4.4 `distill`: write topic files through `BrainRepo.commit_paths`, record
      `commit_sha` and `committed_at_ms` on the stage row. Skipped where the
      brain is unavailable — never a failed night because a rendering target is
      missing.
- [x] 4.5 **Nothing executes generated code.** `build` returns text.

## 5. The entry point

- [x] 5.1 `python -m secondshift.night run` and `run --entry <id>`.
- [x] 5.2 `deploy/spark/second-shift-night.user.timer` + `.service`, mirroring
      the shipped brain-sync pair. **Written, not installed** — installing is
      `operations`, and needs a machine this session cannot reach.
- [x] 5.3 `bash -n` anything shell that gets touched.

## 6. Verification

- [x] 6.1 **The crash test.** Run a night in a subprocess against a stub
      reasoner, kill it mid-walk, reopen the database, assert the completed
      stages survived. **Prove it can fail**: make the loop buffer its stage
      writes to the end and watch it go red.
- [x] 6.2 `close_run` gets its first test, including the refusal-to-double-close
      its docstring has always claimed and nothing has ever checked.
- [x] 6.3 Every terminal path enumerated; assert none leaves a null outcome.
- [x] 6.4 Quarantine: no run, no model call, entry still queued, reason recorded.
- [x] 6.5 Idempotence: dispatching twice produces one run.
- [x] 6.6 The blocking table, exercised row by row.
- [x] 6.7 Full suite, both guards, `openspec validate --strict`.

## 7. Not done here, recorded rather than dropped

- [x] 7.1 **No reaper.** A process killed mid-run leaves an open row. That is
      honest and visible; a reaper would have to guess an outcome and the guess
      would enter the cost curve. `operations` owns the machine and is the layer
      that knows a process died.
- [x] 7.2 **Not run on the Spark.** The prompt's report asks for a real night
      against the real reasoner on a real queued entry. The machine has been
      unreachable for days. This ships tested against a stub and **that is a
      material gap** — a pipeline that has never met the live model is unproven
      where it matters most. First thing to do when the machine returns.


## Mutations run, and what each proved

Each applied, the named test watched go red, then reverted.

| Mutation | Test that went red |
|---|---|
| The walk buffers its stage writes until every stage has run — the all-or-nothing transaction principle 3 names as the violation | `test_stages_completed_before_the_kill_survive_it`, with `KeyError: 'brief'`: nothing survived the kill |
| `close_run` is never called | `test_a_partly_successful_night_closes_degraded` and `test_no_terminal_path_leaves_a_null_outcome` |
| Quarantine opens the run anyway | all three `TestQuarantineRatherThanDowngrade` assertions |
| Uniform blocking — `mockups` needs `research`, `build` needs `mockups` | `test_the_blocking_predicates_are_the_proposal_s_table`, `test_research_is_skipped_and_does_not_stop_what_follows`, `test_critique_is_skipped_when_build_failed` |

The first is the one that matters. Every other test in this file passes against
an implementation that buffers all six stage writes to the end, because they
assert on final state. Only killing the process distinguishes them.

## Two defects found during implementation, not after

- **`_retrieve` returned `ContextPiece` objects where a string was expected.**
  `assemble_context` returns a list; `invoke` calls `.strip()` on what it is
  handed. It would have raised only once an embedder was actually reachable —
  never in this container, and first on the machine. Caught before commit and
  covered by `test_retrieve_returns_text_not_context_pieces`.
- **`stages_for_run` did not select `commit_sha` or `committed_at_ms`.** So the
  commit `distill` now records would have been invisible to the one query
  written to answer "what did the night do." Both are scalars, so adding them
  stays inside the timeline's no-payload rule.

## The failure taxonomy has no entry for a policy refusal

A quarantine is recorded as `orchestrator_crash`, which is what
`telemetry/failures.py`'s own documented fallback rule produces ("classified to
the closest applicable type") and which is **misleading**: a deliberate refusal
is not a crash. The signature is scoped `night.quarantine` so it still groups
distinctly in the ledger.

Adding a `policy_refused` type is a migration, and migrations are the authority
on the data model — beyond a capability whose scope is control flow. **Recorded
for the subject to decide**, not silently resolved.
