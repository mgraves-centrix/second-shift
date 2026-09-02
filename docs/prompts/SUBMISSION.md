# Submission prompt

Paste as the first message of a fresh session.

**The last one. Depends on `JUDGE_MODE.md`, and on the week-8 eval run existing.**

---

Assemble the submission. Read `openspec/constitution.md`, `CLAUDE.md`,
`docs/WEEK_ONE.md` and `docs/SPEC_ROADMAP.md` first; they are the rules, not
background.

## Why this one exists as its own session

**Deadline: Fri 30 Oct 2026, 10:00 PT.** Judged on four equally weighted
criteria, two of which are named in this repository: Technological
Implementation and Design.

Nobody has owned the deliverable. `docs/ARCHITECTURE.md` lists
`NEBIUS_USAGE.md` in its own directory tree with the annotation *evidence doc
for the judging criterion*, and **the file does not exist.** It was a day-7
deliverable in `WEEK_ONE.md` and it did not happen. That is what an unowned
deliverable looks like: named, agreed, and absent for five weeks.

Everything this session produces is read by a judge who will not read the code.

## What already exists — do not invent any of it

- **The week-1 baseline**, recorded 2 Sep:
  `01M1FYFECEXC5ZJEWHNP7WZMXB`, `week_of` 2026-08-31, rubric `b4decd6fe774`,
  brain `ad17b3bcddb6`, six prompts, awaiting scoring. It was **five days late**,
  and its `week_of` says so on purpose. **Do not present it as day 3.** The
  honesty is worth more than the tidiness, and the run pins the brain it actually
  measured.
- Eight numbered ADRs, each recording a decision and what it cost.
- `config/pricing.toml` with rates read from the Token Factory console, so every
  cost figure is reproducible rather than estimated.
- `cost_per_accepted_artifact` and `night_totals` are views, not stored numbers.
- The synthetic night is deterministic by seed, so **every screenshot in the
  submission is reproducible by a judge who clones the repository.**
- `scripts/spikes/*/FINDINGS.md` — four spikes, including two where the
  first-party recipe did not work on the version it named. That is the honest
  engineering record and it is unusual enough to be worth showing.

## The open decision

**What the week-1-versus-week-8 comparison is allowed to claim.**

The centerpiece is the same fixed prompts scored in week 1 and week 8 against a
pinned rubric and pinned brain states. By submission you will have two numbers
and a spread.

**Do not decide what they mean by preference, and do not decide it after seeing
them.** Before scoring week 8, write down what result would falsify the claim —
what difference, given the spread, you would accept as "no improvement." Put that
in the doc *before* the number exists. A threshold chosen after the fact is not
a measurement, and a judge who has run an experiment will know.

If the honest answer turns out to be "the difference is within noise," **say so
and show the spread.** A submission that reports a null result credibly is worth
more than one that reports an improvement nobody can check.

## What good looks like

- **`docs/NEBIUS_USAGE.md`** — what runs on Nebius, why that split and not
  another, and the evidence. ADR 0004's reasoning is the spine: parallel variant
  generation is the strongest use because it is the thing one Spark cannot do,
  and the parallelism is *why the artifact is better*. Numbers from
  `model_calls`, not adjectives.
- A write-up that leads with the interview, because the interview is the product.
- The week-1-to-week-8 chart, with error bars, and the falsification threshold
  stated before the result.
- A demo that a judge can run: a URL, and a repository that clones and passes its
  own gates.
- Every model in the runtime path is an NVIDIA open model — reasoning, speech,
  embedding, TTS. That is a hackathon rule and a stronger answer to Technological
  Implementation than one Nemotron call bolted to a generic stack. Show the
  binding, per role, with the ADR that chose it.
- The failure ledger is shown, not hidden. Six typed failures in a generated
  night, two first-party recipes that did not work, a baseline recorded five days
  late, and a week where the roadmap recorded a gate as met that was never met.
  **A system that records its own failures is the argument.**

## Scope — what NOT to build

- **No new features.** If something is missing at this point it is missing.
- **No retroactive tidying of the record.** Do not rewrite ADRs, delete the late
  baseline, or smooth the roadmap. The record is evidence.
- **No benchmark you cannot reproduce.** Every number cites the query or the
  script that produced it.
- **No claims about the brain you have not diffed.** The topic-file diff is the
  learning claim; if the diff is thin, the claim is thin.

## Constitution hooks

- **Principle 7.** Every number in the submission comes from telemetry that was
  recorded at the time, not reconstructed. `is_synthetic` filtering is what makes
  them true; state that it is applied.
- **Principle 5.** The judge instance is the same code. Say so, and let them
  check.
- **Principle 2.** The privacy argument is the product's central claim. Show the
  `CHECK` constraint, not a paragraph about intent.

## The loop

```bash
git status --short && openspec list && openspec list --specs
apps/api/.venv/bin/python -m pytest apps/api/tests -q
npm --prefix apps/web run test && npm --prefix apps/web run typecheck
scripts/check-no-environment.sh && scripts/check-american-english.sh
```

All green. **A judge cloning a repository whose own gates fail has learned the
most important thing about it in thirty seconds.**

## Verification

- **Clone the repository fresh into a clean directory and run the gates.** Not
  the working copy — a real clone. Bootstrap included.
- Every figure in the submission is regenerated from a command in the document,
  and the command is run to confirm it produces that figure. **Prove the check
  can fail:** change one figure in the text and confirm the regeneration
  disagrees. A citation nobody re-ran is decoration.
- Every screenshot is reproduced from `--seed 42`.
- Follow your own demo instructions on a machine that has never run this, or
  hand them to someone who has not.
- The repository contains no hostnames, addresses, usernames or home paths —
  both check scripts, one more time, on the clone.

## Quality bar

The code is the submission. Judges read this repository.

**Never ship:** a number without a query behind it; a screenshot that cannot be
regenerated; a claim the telemetry does not support; a smoothed-over failure; a
comparison whose threshold was chosen after the result; a `TODO`.

**Always:** cite the source of every figure; show the spread beside the mean;
prefer the honest smaller claim; let the failure record stand. American English.
No hostnames, addresses, usernames or home paths in tracked files.

## Hard stops

- A `[NEEDS CLARIFICATION]` marker. Do not answer your own.
- A constitution violation. Blocking, not advisory.
- **Anything outward-facing** — submitting, publishing, posting, or registering
  anything. Prepare it; the subject submits it.
- Credentials, payment, account settings.
- Rewriting published history or force-pushing.

## Report

1. The falsification threshold, and when you wrote it down relative to seeing the
   number.
2. The week-1-to-week-8 result, with its spread, and whether it clears the
   threshold. **If it does not, say so plainly.**
3. Every figure in the submission, with the command that regenerates it.
4. What the fresh-clone gate run did.
5. What is still missing, ranked by what a judge would notice first.
