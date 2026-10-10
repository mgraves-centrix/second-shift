## 0. Blocked

Two questions in `proposal.md` are unanswered and both change what gets built
rather than how. **Run `/openspec:clarify` before anything below.** They are not
restated here: the rules keep clarification markers out of task lists, because a
task nobody can start yet is not a task.

The first decides what `policy` and `redaction_applied` say on the judge's
`model_calls` row, and whether a `local-only` entry's eval output may be graded
remotely at all. The second decides which reasoner the command resolves.

`2026-10-10-the-judge-is-a-model` is deliberately separate and needs neither
answer, so the judge is not waiting on this.

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

- [ ] 3.1 If the answer departs from `docs/MODELS.md`'s binding of the eval
      judge to the cloud Ultra model, write an ADR superseding it. An accepted
      decision is superseded by a new record, never edited.
- [ ] 3.2 `docs/SPEC_ROADMAP.md`'s `eval-scoring` row says what is left needs
      Token Factory. If the answer is the local reasoner, that row is wrong and
      is the sentence somebody reads when deciding whether a machine session
      can close the week-8 run.

## 4. Gate

- [ ] 4.1 `python3 scripts/gate.py` green, run unpiped.
