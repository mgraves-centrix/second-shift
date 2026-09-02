# Eval scoring prompt

Paste as the first message of a fresh session. Needs a judge model — **check for
one before planning any code.**

**`SUBMISSION.md` depends on this and nothing else produces it.**

---

Score the eval baseline and produce the curve. Read `openspec/constitution.md`,
`CLAUDE.md`, `docs/SPEC_ROADMAP.md` and the `evals` spec first; they are the
rules, not background.

## Why this one

**This is the submission's centerpiece and it had no owner.** The whole thesis is
the same fixed prompts scored in week 1 and week 8 against a pinned rubric and
pinned brain states. `evals` shipped the machinery deliberately without content.
The baseline exists. Nothing scores it, and nothing produces a week-8 run.

`SUBMISSION.md` opens by saying it depends on "the week-8 eval run existing." If
this session does not happen, that dependency is never satisfied and the
submission has one number and no comparison.

## What already exists — do not invent any of it

- **The week-1 baseline**, recorded 2 Sep:
  `01M1FYFECEXC5ZJEWHNP7WZMXB`, `week_of` 2026-08-31, rubric `b4decd6fe774`,
  brain `ad17b3bcddb6`, six active prompts, `judge_model = 'awaiting-scoring'`.
  It was recorded five days past day 3 and its `week_of` says so on purpose.
- `EvalRunner.score(eval_run_id, judge=, generate=, rubric=)` — generates a
  sample per prompt, grades it, records `eval_results` with a `sample_index`.
- **`score` refuses a rubric that is not the one the run pinned.** Added 2 Sep.
  It compares before generating anything and raises `RubricMismatch` naming both
  hashes. Do not route around it; it is the reason a week-8 number will mean
  something.
- `brain_at_baseline(eval_run_id)` reads the brain **at the recorded commit**,
  not the working tree. That is the whole point of the split baseline.
- `Judge` is a protocol with `name`, `version` and
  `score(output=, rubric=, prompt=)`. `Judgement.parse` reads structured
  per-dimension scores and **refuses prose** — an unparseable judgement is a
  typed failure, never a zero, because a zero is a real score meaning "worst
  possible answer."
- `DIMENSIONS` is five, fixed alongside the rubric: `interrogation`, `fit`,
  `judgement`, `actionability`, `voice`.
- `PromptSummary` reports a mean **and a spread**, and `RunSummary.complete` is
  false when any sample failed. A partial run is not comparable to a complete one.
- `docs/MODELS.md` binds the eval judge to Nemotron 3 Ultra, **version-pinned in
  `eval_runs.judge_model_version` and never floating.**

## Check first, and stop if it is absent

The bound judge needs Token Factory. If there is no credential, **do not
substitute a local judge silently.** Report it and stop, or take the open
decision below to the subject first. A curve scored by a different judge than the
one recorded is not the curve the submission claims.

## The open decision

**Whether a local judge is acceptable, and what it costs.**

If Token Factory is unavailable, the fallback is Lightning judging Lightning —
the same model family generating and grading. That is not obviously wrong, and
it is not obviously fine either.

**Do not decide this by preference.** Decide it by measuring: score the same
outputs with both judges, and report the per-dimension disagreement. If they
agree within the sampling spread, say so and the cheap judge is defensible. If
they do not, the curve must state which judge produced it and the comparison is
only valid within one judge.

The second open thing, and it must be settled **before** the week-8 number
exists: **what result would falsify the claim.** Write down the difference you
would accept as "no improvement," given the spread. A threshold chosen after
seeing the number is not a measurement.

## What good looks like

- The week-1 baseline is scored against **the brain commit it pinned**, not
  today's brain. Verify the commit that was actually read.
- The judge is version-pinned on the run, and the pin is a real version string.
- Repeated sampling produces a spread, and the spread is reported everywhere the
  mean is. A difference without error bars is not evidence.
- A failed sample is a typed failure and the run is marked incomplete, rather
  than a zero dragging the mean.
- The week-8 run pins a **different** `brain_sha`. If it pins the same one, the
  brain did not change and the comparison measures nothing — say that plainly
  rather than reporting a number.
- The curve is reproducible: someone with the repository and the database can
  regenerate it from a command.

## Scope — what NOT to build

- **No new rubric.** `config/evals/rubric.md` is pinned by hash. If it must
  change, it is superseded as `rubric-v2.md` and the old runs stay on the old
  one — **never edited in place.**
- **No changing the active prompt set.** Six are pinned by the baseline. Changing
  them invalidates the comparison.
- **No re-recording the week-1 baseline.** It exists, it is late, and its
  lateness is recorded honestly.
- **No new eval dimensions.** Five, fixed alongside the rubric.
- **No scoring by a model that is not version-pinned.**

## Constitution hooks

- **Principle 7.** Every judge call is a recorded model call, so the cost of
  measurement appears in the same accounting as the work measured.
- **Principle 1.** A score is meaningless without the brain state behind it. The
  pinning connects a number to a diff a person can read; that connection is the
  claim.
- **Principle 2.** Eval prompts are authored and held out, carrying no captured
  content — but the *outputs* are generated from the brain, so a cloud judge sees
  brain-derived text. Say whether that is acceptable under the airlock, and if it
  is not, the judge runs locally.

## The loop

```bash
git status --short && openspec list && openspec list --specs
apps/api/.venv/bin/python -m pytest apps/api/tests -q          # 302 pass today
scripts/check-no-environment.sh && scripts/check-american-english.sh
```

On the machine that holds the database and the brain:

```bash
python -m secondshift.evals status     # prints every run's pinned rubric and brain
```

## Verification

- **Scoring under a drifted rubric is refused.** The guard exists; assert it
  rather than assuming. **Prove it can fail:** point `score` at a modified rubric
  and watch it raise, then at the pinned one and watch it proceed.
- The brain content used for generation is the pinned commit's. Move the brain
  forward, re-score, and assert the generated context did not change.
- An unparseable judgement records a typed failure and writes no score.
- The recorded `judge_model_version` is a real version, not a placeholder.
- Re-running scoring does not double-write `eval_results` for the same sample
  index.
- The curve regenerates from a documented command, twice, with the same numbers.

## Quality bar

The code is the submission. Judges read this repository.

**Never ship:** a score from an unpinned judge; a mean without a spread; a
threshold chosen after seeing the result; a rubric edited in place; a zero
standing in for a failed sample; a curve that cannot be regenerated; a `TODO`.

**Always:** report the spread beside the mean; state which judge produced which
number; prefer the honest smaller claim; let failures be loud. American English.
No hostnames, addresses, usernames or home paths in tracked files.

## Hard stops

Stop, record the question with your recommendation, and move on:

- A `[NEEDS CLARIFICATION]` marker. Do not answer your own.
- A constitution violation. Blocking, not advisory.
- **Re-recording or altering the week-1 baseline.** It is the left-hand side of
  the comparison and it is not yours to move.
- **Editing `config/evals/rubric.md`.** Supersede, never edit.
- Credentials, payment, account settings, or anything outward-facing.
- Rewriting published history or force-pushing.

## Report

1. The falsification threshold, and **when you wrote it down relative to seeing
   the number.**
2. The judge decision, with the two-judge disagreement measurement if you made it.
3. The week-1 and week-8 numbers, each with its spread and its `brain_sha`.
4. **Whether the difference clears the threshold. If it does not, say so
   plainly** — a credible null result is worth more than an improvement nobody
   can check.
5. The command that regenerates the curve.
6. Anything blocked, with your recommendation.
