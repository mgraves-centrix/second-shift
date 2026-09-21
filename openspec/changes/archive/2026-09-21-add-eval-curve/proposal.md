# The curve: comparing two eval runs, and refusing to when it would mean nothing

## Scale classification

**L2 — Feature.** One command over rows that already exist, no schema change, no
model call, no credential. It carries a `design.md` because the comparison's
refusals are the substance — what makes a difference evidence rather than a
number — and because one question has to be settled *before* the second number
exists or it cannot be settled honestly at all.

## Why

`SUBMISSION.md` opens by depending on "the week-8 eval run existing", and
`EVAL_SCORING.md` calls this the submission's centerpiece. The thesis is one
sentence: the same fixed prompts, scored in week 1 and week 8, against a pinned
rubric and two pinned brain states, showing that the brain learned something.

The week-1 baseline is recorded — `01M1FYFECEXC5ZJEWHNP7WZMXB`, `week_of`
2026-08-31, rubric `b4decd6fe774`, brain `ad17b3bcddb6`, six active prompts,
`judge_model = 'awaiting-scoring'`. `EvalRunner.summarize` reports one run.

**Nothing compares two.** The centerpiece of the submission is a comparison, and
the comparison has no code. `EVAL_SCORING.md` asks for exactly this — "the curve
is reproducible: someone with the repository and the database can regenerate it
from a command" — and that command does not exist.

## What this change is not

**It does not score anything.** `EVAL_SCORING.md`'s first check is that the
bound judge needs Token Factory and that a local judge must not be substituted
silently. That credential is on the always-on machine, which this session has no
route to, so no scoring happens here and none is faked.

Reading rows that exist is a different act from producing rows that do not. This
command computes over `eval_results` and can say nothing at all when there is
nothing to compare — which, today, is what it says.

## What changes

**`python -m secondshift.evals curve`** — compares two recorded runs and reports
the overall mean, the spread, and the five dimensions separately.

**It refuses more than it reports**, and each refusal is a way the comparison
could otherwise be meaningless:

| Refusal | Why it is not a warning |
|---|---|
| The two runs pin different rubrics | A rubric hash is pinned to a measurement for exactly this reason. Two runs graded by different rubrics are two measurements of different things. |
| The two runs pin the same `brain_sha` | The brain did not change, so the comparison measures sampling noise. `EVAL_SCORING.md`: "say that plainly rather than reporting a number." |
| Either run is incomplete | `RunSummary.complete` is false when a sample failed. A partial run is not comparable to a complete one, and averaging over what survived hides which prompts did not. |
| The two runs were graded by different judges | The curve is only valid within one judge. Stated on the output when it proceeds, refused when they differ. |
| Either run is synthetic | A generated run is a fixture. It is already excluded from `recorded_runs`; this says so rather than silently returning nothing. |

**The difference is reported against the spread**, never alone. A mean that moved
less than the sampling spread has not been shown to have moved.

**Per dimension as well as overall**, read from `eval_results.subscores_json`.
`interrogation` improving while `voice` regresses is the interesting result, and
an overall mean hides it.

## The open decisions

Both are recorded as markers in `design.md`. Neither blocks this command.

**What result would falsify the claim**, written down before the week-8 number
exists. `EVAL_SCORING.md` is explicit that "a threshold chosen after seeing the
number is not a measurement." This is the user's to set and it has a deadline
that is not the submission's: it must be set before the second run is scored.

**Whether a local judge is acceptable if Token Factory is unavailable**, and
what it costs. The prompt says to decide it by measuring per-dimension
disagreement between both judges on the same outputs, not by preference. The
measurement needs both judges and therefore the machine; the protocol for it is
written down here so that session measures rather than designs.

## Impact

**Affected specs:** `evals` (modified — one added requirement).

**Affected code:** `apps/api/secondshift/evals/runner.py`, `__main__.py`. No
schema change, no migration, no route.

## Constitution Compliance

| Principle | Bearing | How this change stands |
|---|---|---|
| 1. Brain plaintext under git | **Constrains** | The comparison is only meaningful because each run pins a brain commit. This reads `brain_sha` and refuses when the two agree; it never reads the working tree, which would compare today's brain against itself. |
| 2. The Privacy Airlock | Not engaged | Reads scores and hashes. No prompt or completion text is read, and none could be — `eval_results` holds a score, subscores and a path. |
| 3. No empty mornings | Not engaged | Nothing here runs during a night. |
| 4. Text-first, voice layered | Not engaged | A command. |
| 5. One codebase, two deployments | **Constrains** | Synthetic runs are excluded from the comparison, as they already are from `recorded_runs`. A judge deployment's seeded rows must never contribute to a measurement, and this is a measurement. |
| 6. Scope boundary | Respected | No new surface. The curve is evidence about the product, not part of it. |
| 7. Telemetry from line one | **Considered, deliberately not applied** | This makes no model call and no agent invocation. It reads rows. A telemetry row for reading a report would record the act of looking at a measurement as part of the measurement. |

No violation. Nothing blocking.

## Risk

**A curve that reports a number nobody should trust.** The whole mitigation is
that it refuses. Every refusal above is a test that must be able to fail, and
the failing case is constructed rather than described.

**A threshold set after the fact.** Recorded as a marker with a deadline earlier
than the submission's, because after the second number exists it cannot be set
honestly at all.
