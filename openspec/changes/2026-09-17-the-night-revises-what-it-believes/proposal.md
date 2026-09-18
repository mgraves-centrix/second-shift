## Scale

**L2 — Feature.** One capability's contract — what a night may change about the
brain — plus a superseding prompt. No design doc; the shape follows from one
asymmetry, stated below.

## Why

ADR 0007 stakes the central claim on the brain rather than the weights, and
names `git diff week1..week8` over the topic files as the artifact a judge
reads. Nothing has ever written that diff. The distiller appends a record of
each night to `nights/` and no line of `profile.md` or `style-guide.md` has
changed since they were seeded, so the evidence for "it learned" would be an
unchanged file.

## What Changes

The distiller proposes beliefs, one sentence each, saying what each supersedes.
They are applied and committed with that night's record, so one night is one
revision and `git show` reads as an argument: what the night learned, and the
lines it changed.

`distiller.v2.md` supersedes v1 rather than editing it, so the pinned hash of
every prior invocation stays readable. It is a draft awaiting the subject's
judgment, like every prompt here.

## The asymmetry the rules follow from

An appended belief that is wrong is visible in a diff and revertible. A
silently deleted one is neither. So:

- a belief replaces a line only where it named exactly one existing line;
- a line that is absent, or present twice, is appended instead of guessed at;
- more than three beliefs in one night are refused whole rather than truncated,
  because taking the first three applies an arbitrary subset of an argument the
  model made as a set;
- a night that proposes nothing changes nothing, which is the normal case.

Skills stay hand-written: they are instructions the system follows, so a wrong
one changes behavior rather than context.

## Constitution Compliance

| Principle | Status | Note |
|---|---|---|
| 1. Brain plaintext under git | **Implements** | The brain's own history becomes the record of what changed and when, one commit per night. |
| 2. Privacy Airlock | Compliant | Topic files keep `local-only` (ADR 0010). What a night proposes is written to the machine, never sent. |
| 3. No empty mornings | Compliant | An unwritable brain still leaves the stage complete, unchanged from before. |
| 4. Text-first | Not applicable | |
| 5. One codebase, two deployments | Compliant | The judge instance revises its own seeded brain the same way. |
| 6. Scope boundary | Compliant | Memory in between, written by the system and read by a person. |
| 7. Telemetry from line one | Compliant | The distill stage's model call is recorded as before; the commit sha is on the stage row. |

No violations.
