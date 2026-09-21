# Design — the curve

## Context

The submission's central claim is a comparison, and comparisons are where
measurements go wrong quietly. This settles what the command computes, what it
refuses, and the two questions that have to be answered by somebody other than
the code.

## Decision 1 — the difference is reported against the spread or not at all

`PromptSummary` already carries a mean and a standard deviation, and its
docstring says why: "a single sample cannot distinguish improvement from
variance, and a difference without a spread is not evidence."

The curve inherits that and makes it structural. There is no output shape that
shows a difference without the spread beside it, because the two-number version
is the one that gets screenshotted.

**What it does not do is decide significance.** With six prompts and a handful
of samples, a t-test would be arithmetic dressed as rigor. The command reports
the difference, both spreads, and whether the difference exceeds the wider of
them — a statement a reader can check by eye and not one that implies a p-value
nobody computed.

## Decision 2 — the refusals, and why each is a refusal rather than a warning

A warning on a report that will be pasted into a submission is a warning nobody
sees. Each of these makes the number mean something other than what it appears
to mean, so each stops the command.

**Different rubrics.** `eval_runs.rubric_sha` exists to pin a measurement to the
text that produced it, and `EvalRunner.score` already refuses to grade against a
rubric a run did not pin. Comparing across that line would undo the guard at the
one point where it matters.

**The same `brain_sha`.** This is the most important one and it is the one most
likely to happen by accident: run the week-8 eval without the brain having
actually moved, and the curve reports sampling noise as a result. The prompt
names it: "say that plainly rather than reporting a number."

**An incomplete run.** `RunSummary.complete` is false when any sample failed,
and a failed sample is a typed failure rather than a zero — precisely so it
cannot drag a mean. Comparing a complete run against a partial one compares six
prompts against however many survived.

**Different judges.** Two judges are two instruments. The prompt allows a local
judge only after measuring the per-dimension disagreement, and even then "the
comparison is only valid within one judge."

**A synthetic run.** Already excluded from `recorded_runs()`. Saying so is the
difference between "no comparison is possible" and an empty report.

## Decision 3 — per dimension, not only overall

`eval_results.subscores_json` holds the five dimensions and nothing reads it
back. An overall mean that moved by 0.4 could be every dimension improving
slightly, or `interrogation` improving substantially while `voice` regresses —
and the second is the more interesting result for a product whose thesis is that
the brain learned this person's judgement.

Reported per dimension and overall. The overall is the headline; the dimensions
are what makes it a finding rather than a number.

## Decision 4 — what would falsify the claim

`EVAL_SCORING.md`: *"what result would falsify the claim. Write down the
difference you would accept as 'no improvement,' given the spread. A threshold
chosen after seeing the number is not a measurement."*

This cannot be decided here and it cannot be decided late. **Its deadline is the
moment before the week-8 run is scored**, which is earlier than the submission's
and is the only reason it is worth raising now rather than with the scoring.

> `[NEEDS CLARIFICATION: What difference between the week-1 and week-8 means
> counts as "no improvement"? Recommendation — state it as a multiple of the
> observed spread rather than as an absolute score, because the spread is not
> known yet and an absolute threshold set today is a guess about a distribution
> nobody has seen. Concretely: "no improvement" is any overall difference
> smaller than the wider of the two runs' standard deviations, and a claimed
> improvement additionally requires at least three of the five dimensions to
> move in the same direction. The second half matters because an overall mean
> can be carried by one dimension, and "the brain learned my judgement" is a
> claim about the whole rubric.]`

**Recording a falsifying result is part of the deal.** If the week-8 number does
not clear the bar, the submission says so with the curve beside it. A thesis
that cannot fail is not a measurement, and a repository that shows the honest
version of its own central claim is making a stronger argument than one that
only reports wins.

## Decision 5 — whether a local judge is acceptable

`docs/MODELS.md` binds the eval judge to Nemotron 3 Ultra, version-pinned in
`eval_runs.judge_model_version`. That needs Token Factory. If it is unavailable,
the fallback is Lightning judging Lightning — the same model family generating
and grading.

The prompt refuses to let this be decided by preference and names the
measurement: score the same outputs with both judges and report the
per-dimension disagreement.

> `[NEEDS CLARIFICATION: If Token Factory is unavailable when the week-8 run is
> scored, is a local judge acceptable? Recommendation — only after running the
> disagreement measurement, and only if the two agree within the sampling
> spread on every dimension. Both runs must then be scored by that same judge,
> including re-scoring week 1, because a curve across two instruments is not a
> curve. If they disagree on any dimension, the submission reports the
> comparison the bound judge produced or reports none; self-grading by the model
> family under test is the weakest sentence available and it is the one a judge
> will notice.]`

**The protocol, so that session measures rather than designs it:** take one
run's recorded outputs, score them with the bound judge and with the local one,
and report the mean per-dimension difference and its spread. Same outputs, same
rubric, same prompts — the only variable is the judge. Anything else measures
the sampling as well as the instrument.

## What is deliberately not built

- **No scoring.** The credential is on the machine and `EVAL_SCORING.md`'s first
  check says stop rather than substitute.
- **No new rubric.** Pinned by hash; a change supersedes as `rubric-v2.md` and
  old runs stay on the old one.
- **No significance test.** Six prompts. See Decision 1.
- **No chart.** The curve is a comparison; rendering it is the submission's
  problem and a number that cannot be read as text is a number that cannot be
  checked.
