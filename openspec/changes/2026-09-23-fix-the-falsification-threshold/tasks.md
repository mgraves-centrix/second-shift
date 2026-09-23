# Tasks — fix the falsification threshold

## 1. The threshold

- [x] 1.1 `config/evals/threshold.md`, dated, with the reasoning and the
      correction to the rule `2026-09-21-add-eval-curve` recommended.
- [ ] 1.2 `load_threshold`, mirroring `load_rubric` — content hash, so the file
      is pinned the way the rubric is.

## 2. Apply it

- [ ] 2.1 `Curve.paired`: one difference per prompt, matched by slug across the
      two runs.
- [ ] 2.2 Refuse two runs scored over different prompt sets. There is no pairing
      across two sets, and the alternative is comparing two different questions.
- [ ] 2.3 `Curve.verdict`: improved, regressed, or no improvement shown, from
      the two conditions the file states.
- [ ] 2.4 The two conditions computed from the paired differences — twice the
      standard error, and two thirds of the prompts moving together.

## 3. Report it

- [ ] 3.1 `curve` prints the verdict, the threshold's hash and the date it was
      fixed, so an edit after the fact is visible where the result is read.
- [ ] 3.2 "No improvement shown" reads as that, never as the claim disproved.
- [ ] 3.3 A regression is reported with the same prominence as an improvement.

## 4. Prove it

- [ ] 4.1 A constructed case for each verdict, with the numbers chosen so the
      rule decides them rather than the fixture being obviously one-sided.
- [ ] 4.2 The case the pairing exists for: one prompt carrying the whole mean,
      which clears an unpaired bar and fails this one.
- [ ] 4.3 Mutations — drop each condition, and swap the standard error for the
      standard deviation, which is the specific error this rule corrects.
- [ ] 4.4 `python3 scripts/gate.py` green, run unpiped.

## 5. Ship

- [ ] 5.1 Sync, archive.
- [ ] 5.2 `docs/NEBIUS_USAGE.md` and `docs/SPEC_ROADMAP.md`: the threshold is
      fixed, and what remains of `eval-scoring` is the run.
