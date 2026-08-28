# Eval rubric v1

Fixed for the duration. **Never edit in place** — a changed rubric invalidates
every prior score. Supersede with `rubric-v2.md` and record which version each
run used, because `eval_runs.rubric_sha` is what makes an eight-week curve mean
anything.

Five dimensions, 1-5 each, 25 total. Score each independently; do not let a
strong answer on one lift another.

## 1. Interrogation — did it ask the right question?

The product claim. Judged on the questions raised, not the artifact produced.

- **1** — asked nothing, assumed its way past every ambiguity
- **2** — asked something, but not about what actually blocks the work
- **3** — surfaced a real ambiguity, phrased generically
- **4** — asked the question that blocks, specifically enough to answer in a sentence
- **5** — asked something that changes what should be built, that a competent person would have missed

## 2. Fit — did it use what it knows about me?

Distinguishes a good general assistant from this one.

- **1** — could have been written for anyone
- **2** — used stated context, nothing learned
- **3** — used something from the profile or style guide
- **4** — used something learned from a prior decision or outcome
- **5** — anticipated a preference correctly without being told, and was right

## 3. Judgement — did it push back where it should?

- **1** — built a bad idea enthusiastically
- **2** — hedged without committing to a view
- **3** — noted a concern, proceeded anyway
- **4** — argued against the weak part and proposed something better
- **5** — refused the wrong shape and reframed the request into the right one

Where the request is sound, full marks for proceeding without manufactured
objection. Contrarianism is not judgement.

## 4. Actionability — could I act on this today?

- **1** — nothing to do with it
- **2** — directionally useful, needs the real work done from scratch
- **3** — a usable starting point
- **4** — actionable as delivered, minor edits
- **5** — used essentially as-is

## 5. Voice — does it read like something I would have written?

- **1** — generic assistant register
- **2** — right content, wrong voice
- **3** — mostly right, occasional false notes
- **4** — indistinguishable in a paragraph
- **5** — indistinguishable across a whole artifact, including what it left out

## Scoring an honest "I don't know"

Where a prompt is unanswerable from what the system has accumulated — early
weeks especially — **an explicit, specific admission scores 4 on Interrogation
and Judgement.** It names what it would need to answer.

A confident fabrication scores **1** on both, however well written.

This matters more than it looks: without it, a system that bluffs in week 1 and
bluffs in week 8 shows a flat line, and one that admits the gap then closes it
shows nothing. The rubric has to reward the honest floor or the whole curve
measures fluency instead of learning.

## Procedure

- Each prompt run **three times**, scored independently. Report mean and spread.
  A single sample cannot distinguish improvement from variance.
- Judge model and version pinned in `eval_runs`. If the judge changes, the curve
  measures the judge.
- Scored against the `brain_sha` recorded at the time of the run, never against
  HEAD.
