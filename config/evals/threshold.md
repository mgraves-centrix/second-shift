# What would falsify the claim

**Fixed 2026-09-23, before any week-8 output existed.** The week-1 baseline
`01M1FYFECEXC5ZJEWHNP7WZMXB` was recorded on 2 Sep and has never been scored, so
at the moment this was written there was exactly one number in the system and it
was nobody's — the baseline's `judge_model` still reads `awaiting-scoring`.

That is the entire reason this file exists and is dated. A threshold chosen
after seeing the result is not a measurement, and a reader can check the claim:
`git log --diff-filter=A -- config/evals/threshold.md` against the commit that
records the week-8 run.

Hashed like the rubric beside it, and `python -m secondshift.evals curve` prints
that hash with its verdict. An edit after the fact changes the hash and is
visible in the same place the result is.

## The claim

The same fixed prompts, generated against two pinned brain states and graded
against one pinned rubric by one pinned judge, produce **better** output in week
8 than in week 1 — and the difference is the brain, because nothing else in the
comparison moved.

## What counts as an improvement

Both conditions, in the same direction:

1. **Magnitude.** The mean per-prompt change exceeds **twice its standard error**
   across the active prompts.
2. **Consistency.** At least **two thirds** of the active prompts move in that
   direction.

Anything else is **"no improvement shown."**

If both conditions are met downward, the honest report is that the brain got
worse, and the submission says so with the same prominence it would have given
the other answer.

## Why these and not something else

**Per prompt, paired.** The unit of comparison is one prompt's mean, not one
sample. The six prompts differ from each other systematically — that is what
makes them a set rather than six draws — so pooling every sample into one
standard deviation mixes the variation *between* prompts into an estimate meant
to capture the variation *within* them. Pairing removes it: the same prompt,
twice, and the difference is the quantity.

**Twice the standard error, not twice the standard deviation.** An earlier draft
of this rule said the difference had to exceed the wider of the two runs'
standard deviations. That was wrong, and wrong in a way worth recording: a
standard deviation describes the spread of samples, not the uncertainty of a
mean, and with eighteen samples per run the two differ by a factor of roughly
four. The old rule would have reported a real and useful improvement as
"not shown", which is not caution — it is a different error.

**Two, not one or three.** One standard error is about 68% and would call noise
a result. Three is a bar this experiment cannot clear on six prompts even if the
brain genuinely helps, which would make the claim unfalsifiable in the other
direction. Two is the conventional rule of thumb and it is stated here as a rule
of thumb: **no p-value is computed and none should be quoted.** Six prompts is
not a sample size that supports one.

**The consistency condition is not redundant, but it is nearly so.** Pairing
already punishes a result carried by one prompt, because one prompt moving alone
inflates the standard deviation of the differences and with it the standard
error. Five prompts at +0.1 and one at +6.0 fails condition 1 on its own. The
second condition is there because the claim is about the *brain*, not about one
kind of question, and a reader should not have to work out that the first
condition implies it.

## What a failure means, precisely

Failing to clear the bar is **"no improvement shown"**, not "the brain learned
nothing." Six prompts and three samples each cannot distinguish a small real
effect from none, and saying otherwise would be claiming a negative result this
design cannot support either.

The honest sentence in that case is the one with the numbers in it: the mean
change, its standard error, how many prompts moved which way, and the spread —
and then the reader decides.

## What would invalidate the comparison outright

Not thresholds — refusals. `python -m secondshift.evals curve` already stops
rather than reporting a number when the two runs pin different rubrics, name
different judges, are incomplete, are synthetic, or pin the same brain state.
Those are not close calls about significance; they are comparisons of different
things.
