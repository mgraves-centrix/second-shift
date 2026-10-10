## 0. Resolved 10 Oct

Both questions are answered in `proposal.md` and this list is no longer blocked.
**The local reasoner grades, `local-only`**, and the cloud judge ADR 0006 named
is retired rather than deferred — ADR 0010 had already made it impermissible,
and the clause has been dead since 2 Sep.

Read the resolution before task 3.1. The ADR this change writes is a correction
rather than a trade-off, and a record that argued the schedule instead would
leave the next reader thinking a cloud judge is a configuration change away.

## 1. The command

- [ ] 1.1 A `score` command in `evals/__main__.py`, taking a run id, resolving
      the judge and the generating reasoner from configuration, and replacing
      the module docstring's statement that scoring is deliberately absent.
- [ ] 1.2 `is_synthetic` from `synthetic_flag()`, never a flag on the command.
      A judge deployment that scored itself into the real curve is
      unrecoverable: the claim is a week-1 to week-8 comparison and there is no
      way to tell afterwards which rows came from where.
- [ ] 1.3 The judge's pinned version read from configuration, recorded in
      `eval_runs.judge_model_version`.
- [ ] 1.4 Missing configuration exits non-zero naming what is missing, rather
      than falling back to a stub. A stub judge that reached the real curve
      would be the one defect in this system that cannot be undone.

## 2. Tests

- [ ] 2.1 `main(["score", ...])` against a temporary database over the stub
      endpoint, asserting the run is scored and the judge recorded by name.
- [ ] 2.2 Missing configuration exits non-zero and writes no `eval_results` row.
- [ ] 2.3 The synthetic flag set makes the command refuse to touch a real run,
      proved against the existing guard rather than re-implemented.

## 3. The record

- [ ] 3.1 An ADR superseding **ADR 0006's eval-judge clause alone**, recording
      that ADR 0010 made a cloud judge impermissible on 2 Sep and that the
      clause has been dead since. The rest of 0006's bindings stand and 0006 is
      not edited. Reaffirm 0010 explicitly: moving the judge to a remote
      provider needs 0010 superseded with an argument, not a flag.
- [ ] 3.2 Record the five-week disagreement as the finding it is — two accepted
      ADRs in force and contradicting each other, surviving because nothing had
      ever been scored, so the dead clause was never executed and never failed.
      It belongs in the ADR's own Context, where the next reader of 0006 will
      follow the supersession link to it.
- [ ] 3.3 `docs/MODELS.md`'s "frontier turns, eval judge" row tabulates the
      retired clause. It is where a reader picks the dead binding back up.
- [ ] 3.4 `docs/SPEC_ROADMAP.md`'s `eval-scoring` row says what is left needs
      Token Factory. It is now false, and it is the sentence somebody reads when
      deciding whether a machine session can close the week-8 run.

## 4. Gate

- [ ] 4.1 `python3 scripts/gate.py` green, run unpiped.
