## Why

"It gets better at being me" is the central claim, and right now nothing measures
it. The tables exist — `eval_prompts`, `eval_runs`, `eval_results` — and nothing
writes them.

The comparison the submission rests on is a fixed set of prompts run in week 1
and week 8, scored against a fixed rubric, with the brain state pinned at each
run. Week 1 is now. Every day without a recorded baseline is a day the left-hand
side of that comparison drifts later, and it cannot be reconstructed afterwards.

The prompts and the rubric are chosen by hand and are not this change's business.
This builds the machinery so that choosing five prompts is data entry.

## What Changes

**A runner** that takes the active prompts, produces an output for each, scores
it against the rubric, and records everything.

**Three samples per prompt**, reported as a mean with its spread. Five prompts
scored once a week is forty-five points of noise with no error bars, and a
week-1-to-week-8 difference indistinguishable from sampling variance is not
evidence of anything.

**Pinning.** `judge_model`, `judge_model_version` and `rubric_sha` are recorded
per run. If the scoring model drifts, an improving curve measures the judge
rather than the brain — and nothing about the output would reveal it.

**Scoring against a recorded brain state, not the current one.** The baseline
splits: the inputs are recorded when no model is available, and scoring happens
later against the `brain_sha` recorded at baseline. Scoring against HEAD would
silently measure a later brain while calling it week 1, understating the delta in
exactly the direction that makes the central claim look weaker.

**The judge is configuration**, not a constant. Which model scores is a decision
with real consequences and it is made by setting a value, not by editing code.
The machinery is exercised against a stub judge, so it is testable and correct
before any real model is chosen.

**Prompts are seeded as candidates.** The ten in `config/evals/candidates.md` are
loaded inactive. Selecting five is marking them active.

Not in this change: choosing the prompts, choosing the judge, or writing the
rubric. Those are judgements about the person being measured.

## Capabilities

### New Capabilities
- `evals`: the measurement spine — running a fixed prompt set against a pinned
  judge and rubric, sampled for variance, attributed to a recorded brain state.

## Constitution Compliance

| Principle | Status | Note |
|---|---|---|
| 1. Brain plaintext under git | **Depends on** | A score is meaningless without the brain state that produced it. Pinning is what connects a number to a diff someone can read. |
| 2. Privacy Airlock | Compliant | Eval prompts are fixed, held-out, and authored deliberately — they carry no captured content, so no policy question arises. The judge call records the policy it ran under like any other. |
| 7. Telemetry from line one | **Implements** | Every judge call is a recorded model call, so the cost of measurement appears in the same accounting as the work being measured. |

No violations.

## Decisions taken without a marker

- **The judge is a configured model, exercised in tests against a stub.** Which
  model is a decision for the person being measured; that it is configurable
  rather than hardcoded is not.
- **Structured scores, not parsed prose.** The judge returns a score per rubric
  dimension. Extracting numbers from free text would make the measurement depend
  on the judge's formatting, which is precisely the drift the pinning exists to
  exclude.
- **A partially failed run records what completed** and is marked incomplete.
  Discarding partial results would throw away real samples; presenting them as
  complete would overstate confidence.
- **An honest "I do not know yet" is a valid output and scores as the rubric
  says.** The rubric already awards it, and a runner that treated it as an error
  would make the early weeks unmeasurable — which is where the interesting part
  of the curve is.
- **Prompts and rubric are content, loaded from files.** Editing a prompt is not
  a code change, and the rubric's hash is what makes a score comparable.

## Impact

**New:** `secondshift/evals/` — loading prompts and rubric, running, scoring,
recording. A command-line entry point.

**Changed:** nothing. The tables already exist; this is the first thing to use
them.

**Risk:** a runner that records a subtly wrong `brain_sha` produces a curve that
looks fine and means nothing. The pinning is the load-bearing part, not the
scoring, and it is tested against a brain that deliberately moves between
baseline and scoring.
