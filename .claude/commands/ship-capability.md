---
name: "Ship Capability"
description: Take the next capability from the spec roadmap through propose, clarify, apply, verify, sync, archive — with commits and pushes at the right boundaries.
category: Workflow
tags: [openspec, workflow, ship]
---

Take one capability from `docs/SPEC_ROADMAP.md` all the way from proposal to
archived, at production quality.

**One capability per invocation.** The workflow has blocking gates that require
human answers by design; batching capabilities would mean either stalling at the
first gate or bulldozing it. Invoke again for the next one.

Argument: a capability name (`/ship-capability capture`). Without one, take the
first unshipped capability in roadmap order and announce it before starting.

---

## Preconditions — check before anything else

Stop and report if any fail. Do not "fix them along the way".

1. `git status --short` is clean, or the only changes are ones this session made.
2. `openspec list` shows no active change. If one exists, resume it rather than
   proposing a new one.
3. The suite is green: `apps/api/.venv/bin/python -m pytest apps/api/tests -q`.
   A red suite before you start means you cannot tell what you broke.
4. `openspec validate --specs --strict` passes.

Report the four results in one line each, then proceed.

---

## Phase 1 — Ground the proposal

Read, in this order: the capability's entry in `docs/SPEC_ROADMAP.md`, then
`openspec/constitution.md`, then the ADRs the roadmap entry cites, then the
canonical specs in `openspec/specs/` for anything adjacent.

The roadmap entry separates **decided** from **open**. Decided items are
settled — draw on them, do not re-derive or re-litigate them. Open items become
clarification markers, never assumptions.

**Delegate the survey when it spans more than three files.** Send an `Explore`
agent to map existing code, naming conventions and adjacent requirements, and
work from its findings. Run independent surveys concurrently in one message.
Do not delegate the *writing* — a proposal is an argument, and arguments do not
survive being assembled from summaries.

## Phase 2 — Propose

Invoke `/opsx:propose`. Its rules already enforce scale classification,
constitution checking and marker limits; follow them rather than restating them.

Two things the rules cannot check for you:

- **Every open item from the roadmap becomes a marker or a decision.** If you
  find yourself writing "we will use X" for an item the roadmap listed as open,
  stop: that is an assumption wearing a decision's clothes.
- **Requirements are behaviour, not implementation.** "The system SHALL reject a
  replayed offline capture" is a requirement. "Use a UUID idempotency key" is a
  design note. Wrong altitude here poisons every later change.

Then: `openspec validate <change> --strict`, and commit the proposal.

Commit message body explains *why this shape*, not what the files contain — the
diff already shows that.

## Phase 3 — Clarify — **HARD STOP**

If the change has any `[NEEDS CLARIFICATION]` markers, run `/openspec:clarify`
and **stop for the user's answers**.

Do not answer markers yourself. Do not pick "the obvious default". Do not
proceed on the ones that seem minor. The marker exists because the answer
changes the work, and a marker resolved by assumption is worse than no marker at
all — it launders a guess into a recorded decision.

You may recommend an option and say why. The choice is the user's.

After answers: fold them into the proposal, the design doc **and the spec
deltas**. Deltas are what merge into canonical specs at archive, so a decision
that lands only in the proposal is a decision that quietly disappears. Commit.

## Phase 4 — Apply

Invoke `/opsx:apply`. Work tasks in order. Mark `- [x]` only when the specified
behaviour is fully implemented — not when it is close, not when the test is
written but skipped.

**Commit per task group, not per task and not at the end.** A task group is a
coherent unit that leaves the suite green. Push at the end of the phase, not on
every commit.

**Delegate implementation only where the work is genuinely independent** — an
isolated module with a clear interface and its own tests. Give the agent the
relevant spec requirements verbatim, the quality bar below, and the surrounding
conventions. Review what comes back against the spec before committing it; you
own the result, and an agent's output is a draft, not a merge.

Do not delegate: anything touching the airlock, the telemetry recorder, or
migrations. Those are load-bearing for constitution principles and need one
person's judgment end to end.

**Stop and ask** if implementation reveals the spec is wrong, a task needs work
beyond what it describes, or you are tempted to narrow scope to make something
fit. Surface it. Never absorb it silently.

## Phase 5 — Verify

Not "the tests pass". Verify in this order:

1. Full suite green locally.
2. `openspec validate <change> --strict`.
3. **Run on the Spark.** `COPYFILE_DISABLE=1 tar` (AppleDouble sidecars break
   migration discovery and the source scan), transfer to a scratch directory,
   build a venv with `python -m venv`, install with `-c constraints.txt`, run
   the full suite. Python there is 3.12.3 on aarch64; local dev is newer, and
   that gap has already produced two defects that passed locally.
   **Never `uv run` on the Spark** — it re-resolves the environment to x86_64
   and destroys it.
4. Exercise the capability against reality where it has a real-world surface —
   the live capability probe, an actual endpoint, a real file round-trip. A
   green unit suite is not evidence that the thing works on the machine.
5. Clean up whatever you created on the Spark, and say what you removed.

Report failures with the actual output. Never summarise a failure into a
reassurance.

## Phase 6 — Archive

Invoke `/opsx:archive`. Sync deltas into canonical specs, verify every ADDED
requirement and scenario is present in its main spec **before** anything moves,
then archive.

Before archiving, ask the question the archive guidance asks: did this change
establish an architectural decision that lives only in `design.md`? That file is
about to move out of the discoverable path. If yes, write the ADR first.

Commit and push.

## Phase 7 — Close the loop

- Update `docs/SPEC_ROADMAP.md`: mark shipped, and revise later entries with
  anything learned that changes them.
- Update `docs/WEEK_ONE.md` if the day's gates moved.
- Record any obligation you deferred **in the next capability's roadmap entry**,
  not only in this change's design doc. A deferred obligation with no home is a
  dropped one.
- Report: what shipped, what it cost, what surprised you, what the next
  capability inherits.

---

## The quality bar

The code you write is the submission. Judges read the repository.

**Never ship:**

- `TODO`, `FIXME`, `pass  # implement later`, or a function that returns a
  plausible constant instead of doing the work.
- A test that cannot fail. If deleting the implementation still leaves it green,
  it is decoration. Assert on values, not on `is not None`.
- A mock of the thing under test. Mock the network; never mock your own logic
  and then claim it works.
- A broad `except Exception` that exists to make a test pass.
- A docstring restating the signature. Explain *why*, the constraint that shaped
  it, or the trap the next reader will hit. If there is nothing to say, say
  nothing.
- Comments narrating what the line does. The code says that already.
- An API you have not verified exists. Check the installed package before
  calling it — invented method names are the most expensive kind of slop
  because they look right.
- A commit with a failing or skipped test, or a task marked `[x]` that is not
  done.

**Always:**

- Match the surrounding code's idiom, naming and comment density. New code
  should be unidentifiable as new.
- Write the test that would have caught the bug, not the test that passes.
- Prefer the boring construction. Cleverness is a cost paid by whoever reads it
  at 2am — which, on this project, is a machine.
- Name the trade-off in a comment when you take a non-obvious path. `# derived,
  not stored: release is then automatic` earns its line.
- Keep provider specifics inside `providers/`. Keep telemetry writes inside the
  recorder's lock. Keep tables append-only.
- Let a failure be loud. A silent zero in a scored measurement is worse than a
  crash.

## Using agents well

Good delegation: parallel surveys of unfamiliar code; independent
implementation of an isolated module with its own tests; an adversarial review
pass asking "what does this spec fail to say"; drafting several approaches to
compare.

Bad delegation: anything requiring taste or the user's context; the airlock,
recorder or migrations; writing the proposal argument; deciding what a
clarification marker means.

Launch independent agents in one message so they run concurrently. Review
everything they return against the spec — you are accountable for it.

## Commit and push protocol

- Commit at meaningful boundaries: proposal, each clarification round, each task
  group, archive. Not every file save.
- Push at phase ends. Never mid-phase with a red suite.
- Messages: why, not what. State what was rejected and why, when a real
  alternative was considered.
- Never rewrite pushed history.
- The remote is `mgraves-centrix`. **Never push to `master` or `main` on any
  `ditinc` remote** — that rule stands regardless of this workflow.
