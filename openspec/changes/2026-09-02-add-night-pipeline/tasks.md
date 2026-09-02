# Tasks — `night-pipeline`

## 1. The stage table, as code

- [ ] 1.1 `secondshift/night/stages.py`: the six stages in schema order, each
      with its agent role and a `can_run(completed)` predicate. It must read as
      the proposal's table — that table is the specification.
- [ ] 1.2 Assert the role map against `agents.roster.permitted_roles(conn)`, so
      a role renamed in the schema fails here rather than at 2am.
- [ ] 1.3 Assert the stage names against the `run_stages` CHECK constraint, read
      from `sqlite_master` — the same technique `roster.permitted_roles` uses.
      A seventh stage added to the schema with no definition must fail.

## 2. Policy resolution and quarantine

- [ ] 2.1 Resolve once per entry, before any run row exists.
- [ ] 2.2 Where not permitted: record a typed failure, leave the entry queued,
      open nothing. Assert no `runs` row and no `model_calls` row.
- [ ] 2.3 Test the concrete trap: a `local-only` entry on a `cloud` profile must
      not reach `EchoReasoner`.

## 3. The loop

- [ ] 3.1 `secondshift/night/run.py`: open the run, transition the entry to
      `running`, walk the stages, close the run.
- [ ] 3.2 Each stage in its own transaction — insert `running`, invoke,
      `complete_run_stage`. No enclosing transaction.
- [ ] 3.3 A stage that raises is recorded `failed` with a typed failure, and the
      walk continues per the predicates.
- [ ] 3.4 Outcome derived at close: `complete`, `degraded`, or `failed`.
- [ ] 3.5 `close_run` on every terminal path, including the exception path.
- [ ] 3.6 On failure, entry returns to `queued`.

## 4. The stages themselves

- [ ] 4.1 `brief`: entry text plus `assemble_context` where retrieval is
      available; where it is not, the entry text alone **and the brief says so**.
- [ ] 4.2 `research`: skipped with "no research provider is configured" until
      `research` ships. Skipped, never failed — nothing was attempted.
- [ ] 4.3 `mockups`, `build`, `critique`: invoke their roles on what completed.
- [ ] 4.4 `distill`: write topic files through `BrainRepo.commit_paths`, record
      `commit_sha` and `committed_at_ms` on the stage row. Skipped where the
      brain is unavailable — never a failed night because a rendering target is
      missing.
- [ ] 4.5 **Nothing executes generated code.** `build` returns text.

## 5. The entry point

- [ ] 5.1 `python -m secondshift.night run` and `run --entry <id>`.
- [ ] 5.2 `deploy/spark/second-shift-night.user.timer` + `.service`, mirroring
      the shipped brain-sync pair. **Written, not installed** — installing is
      `operations`, and needs a machine this session cannot reach.
- [ ] 5.3 `bash -n` anything shell that gets touched.

## 6. Verification

- [ ] 6.1 **The crash test.** Run a night in a subprocess against a stub
      reasoner, kill it mid-walk, reopen the database, assert the completed
      stages survived. **Prove it can fail**: make the loop buffer its stage
      writes to the end and watch it go red.
- [ ] 6.2 `close_run` gets its first test, including the refusal-to-double-close
      its docstring has always claimed and nothing has ever checked.
- [ ] 6.3 Every terminal path enumerated; assert none leaves a null outcome.
- [ ] 6.4 Quarantine: no run, no model call, entry still queued, reason recorded.
- [ ] 6.5 Idempotence: dispatching twice produces one run.
- [ ] 6.6 The blocking table, exercised row by row.
- [ ] 6.7 Full suite, both guards, `openspec validate --strict`.

## 7. Not done here, recorded rather than dropped

- [ ] 7.1 **No reaper.** A process killed mid-run leaves an open row. That is
      honest and visible; a reaper would have to guess an outcome and the guess
      would enter the cost curve. `operations` owns the machine and is the layer
      that knows a process died.
- [ ] 7.2 **Not run on the Spark.** The prompt's report asks for a real night
      against the real reasoner on a real queued entry. The machine has been
      unreachable for days. This ships tested against a stub and **that is a
      material gap** — a pipeline that has never met the live model is unproven
      where it matters most. First thing to do when the machine returns.
