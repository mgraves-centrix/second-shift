# Tasks — the curve

Neither marker blocks this. The falsification threshold is the user's and its
deadline is before the week-8 run is scored, not before this ships; the judge
question needs a credential this session does not have.

## 1. The comparison

- [x] 1.1 `Curve` and `DimensionDelta`: the two runs, the overall means and
      spreads, and the five dimensions separately, read from
      `eval_results.subscores_json` — which nothing has read back until now.
- [x] 1.2 `EvalRunner.curve(earlier, later)` returning it, over
      `summarize`'s existing per-prompt samples rather than a second query path.
- [x] 1.3 A difference smaller than the wider spread reads as "not shown to have
      moved". There is no output shape that shows a difference without both
      spreads beside it.

## 2. The refusals, which are the substance

Each is its own exception type, and each gets a test that constructs the failing
case rather than describing it.

- [x] 2.1 Different rubrics.
- [x] 2.2 The same `brain_sha` — the one most likely to happen by accident, and
      the one `EVAL_SCORING.md` names explicitly.
- [x] 2.3 Either run incomplete.
- [x] 2.4 Different judges.
- [x] 2.5 Either run synthetic.
- [x] 2.6 A run that does not exist, and a run with no results at all.

## 3. The command

- [x] 3.1 `python -m secondshift.evals curve <earlier> <later>`, and with no
      arguments the two oldest and newest complete real runs.
- [x] 3.2 Non-zero exit on a refusal, with the reason on stderr — the same
      shape `status` already uses, where the exit code is part of the report.
- [x] 3.3 Run it against the real database's recorded state and report what it
      says today, which is that there is nothing to compare yet.

## 4. Prove it

- [x] 4.1 Every refusal fails when its condition holds and passes when it does
      not. A guard that cannot go red reads as evidence.
- [x] 4.2 The dimension breakdown catches a regression hidden by an improving
      overall mean — constructed, because that is the case the breakdown exists
      for and it will not occur by accident in a fixture.
- [x] 4.3 `python3 scripts/gate.py` green, run unpiped.

## 5. Ship

- [ ] 5.1 Sync, archive.
- [ ] 5.2 `docs/SPEC_ROADMAP.md`: what is left of `eval-scoring` after this, and
      that the falsification threshold has a deadline earlier than the
      submission's.
