# Night pipeline prompt

> **✅ Shipped 2 Sep — `openspec/changes/archive/2026-09-02-add-night-pipeline`.**
> Kept as the record of what was asked. Two things are worth carrying forward:
>
> 1. **Its report asks for a real night on the Spark and that did not happen.**
>    The machine has been unreachable for days. The pipeline ships tested
>    against a stub and has never met the live reasoner — a material gap, and
>    the first thing to do when the machine returns.
> 2. **Its open decision was the right question**, and the answer was
>    non-uniform exactly as it predicted: two blocking edges, and `distill`
>    whose predicate is over the whole run rather than any predecessor.

Paste as the first message of a fresh session. Local to build; the Spark to run
it for real.

**Depends on `CONFIGURATION.md` and `AGENTS.md`. Both landed 2 Sep, along with
`RETRIEVAL.md`. All three prerequisites are met.**

---

Build `night-pipeline`. Read `openspec/constitution.md`, `CLAUDE.md`, and
`docs/SPEC_ROADMAP.md` first; they are the rules, not background.

## Why this one

This is the product's verb. Everything shipped so far captures, stores, measures
or renders; nothing has ever *done the work overnight*.

Nothing has ever processed a captured entry. `run_stages` has no writer outside
the synthetic seed, and `Repository.close_run` has no caller anywhere in the
tree — not even a test.

> **The counts that were here are unverifiable from a development container.**
> This said "three real entries queued since 28 Aug, `runs` holds zero rows,"
> which was read off the always-on machine on 2 Sep and has not been re-read
> since — the machine has been unreachable. Query it rather than quoting this:
> `SELECT status, COUNT(*) FROM entries GROUP BY status;` and
> `SELECT COUNT(*) FROM runs;`. What is verifiable from the repository is the
> statement above it, and that is the argument.

**Principle 3 is executable behavior, and it lives here.** "No empty mornings" is
not a schema affordance — `run_stages` exists and nothing writes it. This is the
capability that makes the principle true or leaves it decorative.

## What already exists — do not invent any of it

- `run_stages`: `stage` CHECK over `brief`, `research`, `mockups`, `build`,
  `critique`, `distill`; `seq`; `status` CHECK over `pending`, `running`,
  `complete`, `failed`, `skipped`; `started_at_ms`, `ended_at_ms`,
  `committed_at_ms`, `commit_sha`; `UNIQUE(run_id, stage)`.
- `runs`: `outcome` CHECK over `complete`, `degraded`, `failed`, `aborted`;
  `furthest_stage`; `effective_policy`; `policy_source`; `brain_sha`.
- **`Repository.close_run` exists, has no caller, and has no test.** Verified by
  scanning the tree on 2 Sep: the only other mention is a comment in
  `repository.py` noting the absence. Every recorded run is permanently in
  flight, with a null outcome and no end time; `night-timeline` reads around it
  through `run_stages`. Its docstring claims it "refuses to close one that is
  already closed" — nothing has ever checked that. Give it a caller **and** a
  test.
- `dispatch_eligible_entries()` screens for queued, non-synthetic, non-empty —
  and `ineligible_entries()` returns the rest *with a reason each*, because an
  entry that can never run must not be silently invisible.
- Entry transitions are a fixed set: `captured→queued`, `queued→running`,
  `running→answered`, `running→queued`, `answered→archived`, `queued→archived`.
  **There is no failed state for an entry.** A run that fails returns its entry
  to `queued`, which is a design decision already taken — respect it.
- `resolve_policy(entry_default, available=, unavailable_reason=,
  upgrade_decision_id=)` returns a `PolicyResolution` and refuses to widen
  `local-only` without an attributable decision. Where the profile cannot honor
  the policy, it returns `permitted=False` and the caller **quarantines rather
  than downgrading**.
- `Recorder.invocation(...)` nests by contextvar. Depth and parentage are free.
- The synthetic generator writes a night of the right shape and deliberately
  leaves its final stage `running` — that is your degraded-render test case, and
  it is already in the data.
- A systemd user timer pattern exists: `deploy/spark/second-shift-brain-sync.user.timer`.

## The open decision

**Which stages block their successors, and which are skippable.**

Principle 3 says a late failure must still leave every earlier stage's output
presented. That settles what happens *after* a failure. It does not settle
whether `build` may run when `research` failed — and the honest answer is
different per pair. `mockups` without `research` is degraded but real.
`critique` without anything to critique is not.

**Do not decide this by preference and do not impose one uniform rule.** Build
the table: for each of the six stages, what it consumes, and what it can produce
when that input is missing or partial. The pairs where the answer is "produces
nothing useful" are the blocking ones. Put the table in the proposal.

The second open thing: **what starts a night.** A timer, a manual command, or
both. Whichever you propose, the manual path must exist — a pipeline you cannot
run on demand is one you cannot debug at 2am.

## What good looks like

- A stage commits its output **as it completes**, in its own transaction. Not at
  the end, not in a batch. Kill the process mid-run and every completed stage is
  still there, still readable, still rendered by the scrubber.
- A failed stage records `failed` with a typed failure, and the run continues
  wherever the table above says it can.
- `close_run` is called on every terminal path — complete, degraded, failed,
  aborted — including the one where the process died and something later reaps it.
- A run under `local-only` on a profile that cannot honor it is **quarantined,
  not downgraded**. The reason is recorded and readable.
- The morning after a half-failed night shows what succeeded. That is the whole
  point and it is testable without a UI.
- Running it twice over the same entry does not produce two runs.

## Scope — what NOT to build

- **No morning interview.** This produces; `MORNING_INTERVIEW.md` presents.
- **No retrieval and no research.** Stages call what exists; if `retrieval` has
  not landed, the brief stage takes the entry text and says so.
- **No artifact rendering.** `ARTIFACTS.md` owns what a brief looks like on disk.
  *(Shipped 2 Sep and wired into these stages: each one that produces something
  now writes it through `artifacts.store`. The boundary held — the pipeline
  calls the writer and owns none of the layout.)*
- **No new stages.** Six, fixed by a database CHECK.
- **Nothing runs generated code.** `NOT_BUILDING.md` excludes autonomous
  execution of generated code, and a build stage that executes its own output
  has crossed it.

## Constitution hooks

- **Principle 3 governs and is the reason this capability exists.** A stage that
  holds its output until the run completes is a violation, not a design choice.
- **Principle 2.** Policy resolution happens once, per run, before any provider
  call, and the resolution is recorded on the run. A `local-only` night never
  reaches a remote provider — refused at the call and unrecordable at the
  database.
- **Principle 7.** Every stage opens invocations; every model call is recorded.
  A stage that ran and left no trace is indistinguishable from one that was
  skipped.
- **Principle 6.** The pipeline does not grow a queue UI, a retry button or a
  priority field. `decisions` and `entries` carry the only state the loop needs.

## The loop

```bash
git status --short && openspec list && openspec list --specs
apps/api/.venv/bin/python -m pytest apps/api/tests -q          # 395 pass today
npm --prefix apps/web run test && npm --prefix apps/web run typecheck
scripts/check-no-environment.sh && scripts/check-american-english.sh
```

All green before starting. Then propose, clarify, apply, verify, sync, archive.

## Verification — kill it in the middle

A green suite does not prove checkpointing. Prove it two ways.

- **Crash it.** Run a night against a stub reasoner, kill the process after stage
  three, reopen the database, and assert stages one to three are `complete` with
  their artifacts present. This is the principle-3 test and it must be able to
  fail: make a stage buffer its write until the end and watch it go red.
- **Fail one stage.** Assert the run reaches `degraded`, later stages behave as
  your table says, and the failure is typed and attributable.
- **`close_run` is called on every terminal path.** Enumerate them; assert no
  path leaves a null outcome. This is the defect that already exists — do not
  reintroduce it.
- A `local-only` entry on a cloud-only profile is quarantined with a reason, and
  no model call row exists for it.
- Re-running over the same entry is idempotent.
- Then run it **on the Spark against the real reasoner**, on one of the three
  entries that have been queued since 28 Aug, and paste what came out.

## Quality bar

The code is the submission. Judges read this repository.

**Never ship:** a `TODO`; a stage that returns a plausible constant; a test that
passes with the implementation deleted; a broad `except` that turns a failure
into a skip; an all-or-nothing transaction across stages; a run left with a null
outcome; a `[x]` on a task that is not done.

**Always:** match the surrounding idiom; write the test that would have caught
the bug; keep provider specifics inside `providers/`; keep writes inside the
recorder's lock; keep tables append-only; let failures be loud. American
English. No hostnames, addresses, usernames or home paths in tracked files.

## Hard stops

Stop, record the question with your recommendation, and move on:

- A `[NEEDS CLARIFICATION]` marker. Do not answer your own.
- A constitution violation. Blocking, not advisory.
- Anything in `NOT_BUILDING.md`.
- Credentials, payment, account settings, or anything outward-facing.
- Rewriting published history or force-pushing.

**Capture is live and taking real ideas.** Prove it still works after anything
you deploy. If it breaks and you cannot fix it in ten minutes, revert to the last
known-good commit, redeploy, verify, and stop.

## Report

1. The blocking table, and which pairs you found were genuinely skippable.
2. The crash test — where you killed it, and what survived.
3. What shipped, with test counts.
4. The real night you ran on the Spark, and what it produced. If the output is
   poor, say so — a pipeline that runs and produces nothing worth reading is a
   finding, not a success.
5. Anything blocked, with your recommendation.
6. What you would do next, and why that rather than the alternative.
