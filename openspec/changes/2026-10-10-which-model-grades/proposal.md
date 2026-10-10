# Which model grades, and under which policy

## Scale classification

**L2 — Feature.** One capability (`evals`), one file
(`evals/__main__.py`), under a day — once the two questions below are answered.
It is separate from `2026-10-10-the-judge-is-a-model` because the apply gate
blocks implementation while a clarification marker stands, and `ModelJudge`
itself needs neither answer.

## Why

`ModelJudge` takes a `Reasoner` and a policy. Something has to choose them, and
the choice is not a coding decision.

## The open decision

**Which model grades, and under which policy.**

`docs/MODELS.md` binds the eval judge to `Nemotron-3-Ultra-550B-a55B` via Token
Factory, and says it is version-pinned in `eval_runs.judge_model_version` and
never floats. That is a decision of record and this change does not overturn it.
But it was made on 27 Aug for judgment quality, and two things about it are now
worth re-examining rather than inheriting:

**It makes the centerpiece depend on a credential.** The key exists on the
always-on machine and nowhere else. A local judge needs no key, and the machine
session that the week-8 run requires anyway — the local reasoner generates the
outputs — would then close the whole thing.

**It sends brain-derived text to a remote provider.** An eval output is
generated from the brain at a pinned commit. Principle 2 says the brain itself
never leaves and only assembled, policy-filtered context is transmitted. An
output is not the brain, and it is not retrieval context either; it is model
text about the subject's own ideas. Nothing in `openspec/specs/privacy-airlock/`
or `docs/decisions/` says which of those it counts as, and the judge's
`model_calls` row has to carry a policy either way.

The argument the other way is judgment quality: a 550B grader is a better
instrument than a 30B one. The counter is that the curve uses **differences**,
not levels, and the judge is pinned across both runs — so a consistent judge
matters and an excellent one is a bonus. A 30B model emitting five integers
against a written rubric is not the hard end of its range.

- [NEEDS CLARIFICATION: Does an eval output sent to a cloud judge require
  redaction before egress, or is it `cloud-assisted` text the airlock already
  permits? The judge's `model_calls` row records `policy` and
  `redaction_applied`, so this decides what those two columns say — and whether
  a `local-only` entry's eval output may be graded remotely at all.]
- [NEEDS CLARIFICATION: Is the judge the cloud Ultra model as `docs/MODELS.md`
  binds it, or the local reasoner? Recommendation: **the local reasoner for the
  week-1 and week-8 runs**, because it removes the credential from the critical
  path with eleven days to the window, needs no answer to the question above,
  and the comparison is of differences under a pinned judge rather than of
  absolute scores. Revisit for a later run if the grader looks like the limit.]

**Neither marker blocks what this change builds.** `ModelJudge` takes a
`Reasoner` and a policy; both answers are a constructor argument. What they
block is the `score` command's default and the deployment note, so those are the
tasks held back until `/openspec:clarify` resolves them.

## What this change is not

- **Not the judge.** `2026-10-10-the-judge-is-a-model` builds and tests that.
- **Not a Nebius provider.** If the answer is the cloud judge, the Token Factory
  `Reasoner` is `nebius-executor`'s to build, and this change consumes it.

## What changes

1. **A `score` command** in `evals/__main__.py`, resolving the judge and the
   generating reasoner from configuration, so a recorded baseline can be
   generated and graded outside the test suite. `EvalRunner.score` is currently
   called from nowhere but `apps/api/tests/test_evals.py`, and that module's
   docstring says scoring is "deliberately absent from this entry point until a
   judge is chosen and a generating provider is configured" — the condition the
   first answer ends.

2. **The judge's pinned version** recorded in `eval_runs.judge_model_version`,
   from configuration rather than from whatever the endpoint reports, because
   `docs/MODELS.md` says it never floats.

3. **`is_synthetic` stays server-derived.** A judge deployment that scored
   itself into the real curve is unrecoverable, and the command takes no flag
   that could do it.

4. **An ADR if the answer departs from `docs/MODELS.md`**, which binds the eval
   judge to the cloud Ultra model. Superseding that binding is a new decision
   record, never an edit to the old one.

## Impact

- `apps/api/secondshift/evals/__main__.py` — the `score` command.
- `config/models.toml` — the judge binding, if it is configuration.
- `docs/MODELS.md`, `docs/decisions/` — if the binding changes.

## Constitution Compliance

- **Principle 2 (Privacy Airlock).** The first marker *is* this principle. No
  implementation proceeds until it is answered; that is the point of the split.
- **Principle 5 (one codebase, two deployments).** The judge is configuration,
  so the judge deployment and the personal one differ by configuration and
  seeded data rather than by code.
- **Principle 7 (telemetry from line one).** The judge's model call is recorded
  by `Reasoner.complete`. No new instrumentation is owed.
- Principles 1, 3, 4 and 6 are untouched: no brain write, no night path, no
  interaction surface, and nothing outside `evals`.

## Risk

**The window.** Week 8 is 15–21 Oct. Both runs must be generated and scored with
the same judge on both sides, and the curve refuses two judges as two
instruments. An answer after 15 Oct does not leave room to discover that the
chosen judge needs its prompt reworked.
