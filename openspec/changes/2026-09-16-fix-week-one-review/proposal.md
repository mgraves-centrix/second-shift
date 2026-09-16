## Scale

**L1 — Small task.** Every change here restores behavior a shipped capability
already claimed, found by a four-reviewer board before merging the week-one
branch. It is recorded as a change rather than fixed silently because four of
the fixes alter a stated contract — a queued answer returns its idea to the
queue, a `cloud` deployment refuses to start a night, a conflicting answer is a
conflict rather than not-found, and an interrupted night is recovered — and a
spec that does not say so is a spec a later session will re-derive wrongly.

## Why

The board found the morning loop could not close and leaked across ideas, and
the night could consume ideas it had not worked:

- Queued answers were taken by whichever entry ran first, so a `local-only`
  answer became a `cloud-assisted` idea's context under that idea's policy.
- An answer queued for tonight had no night to reach: questions are raised
  after the run moves its entry to `answered`, and nothing moved it back.
- The interviewer was shown every run since the last answered decision, across
  entries, under one run's policy.
- Stage failures and search calls were recorded with no run, so the morning
  never said why a stage failed and research spend summed to zero.
- On `cloud` the night ran against an echo reasoner, closing stages `complete`
  with the prompt as the artifact.
- A killed night left its entry `running`, dispatched and listed by nothing.
- The search query carried hosts, keys and names past redaction.

## What Changes

The fixes, each with its regression test, are the commits this change
accompanies. The requirements below are the ones they add.

## A decision this reverses

`2026-09-02-add-night-pipeline` task 7.1 chose **no reaper**: a process killed
mid-run leaves an open row, which it called honest and visible, and a reaper
"would have to guess an outcome and the guess would enter the cost curve."

Both halves turned out not to hold. The open row was visible; the *idea* was
not — its entry sat in `running`, which dispatch skips and the not-dispatched
report does not list, so the idea silently stopped being worked. And with a
one-night-at-a-time lock the outcome is not a guess: an open run with the lock
free belongs to a process that is gone, and nothing proves any unfinished stage
completed. Recording it `failed` is the observation, not an estimate. Stages
that did complete keep their own end times and outcomes.

No ADR recorded the original choice, so none is superseded.

## Constitution Compliance

| Principle | Status | Note |
|---|---|---|
| 1. Brain plaintext under git | Not applicable | |
| 2. Privacy Airlock | **Implements** | Answers and interview facts are scoped to their own entry and run, so no idea's material reaches another idea's policy; the search query refuses hosts, identifiers and unlisted opening capitals. Neither guard gains a bypass. |
| 3. No empty mornings | **Implements** | A failed stage says why; an interrupted night is recovered rather than lost; one entry's defect no longer ends the night. |
| 4. Text-first | Not applicable | |
| 5. One codebase, two deployments | **Constrains** | The `cloud` refusal applies until a cloud reasoner exists; `nebius-executor` lifts it by binding one. |
| 6. Scope boundary | Compliant | An answer is still accepted only against a decision id. |
| 7. Telemetry from line one | **Implements** | Failures and tool calls recorded outside an invocation now name their run. |

No violations.
