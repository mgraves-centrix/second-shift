## 0. Resolved 10 Oct

Both questions are answered in `proposal.md` and this list is no longer blocked.
**The local reasoner grades, `local-only`**, and the cloud judge ADR 0006 named
is retired rather than deferred — ADR 0010 had already made it impermissible,
and the clause has been dead since 2 Sep.

Read the resolution before task 3.1. The ADR this change writes is a correction
rather than a trade-off, and a record that argued the schedule instead would
leave the next reader thinking a cloud judge is a configuration change away.

## 1. The command

- [x] 1.1 A `score` command in `evals/__main__.py`, taking a run id, resolving
      the judge and the generating reasoner from configuration, and replacing
      the module docstring's statement that scoring is deliberately absent.
- [x] 1.2 `is_synthetic` from `synthetic_flag()`, never a flag on the command.
      A judge deployment that scored itself into the real curve is
      unrecoverable: the claim is a week-1 to week-8 comparison and there is no
      way to tell afterwards which rows came from where.
- [x] 1.3 The judge's pinned version read from configuration, recorded in
      `eval_runs.judge_model_version`.
- [x] 1.4 Missing configuration exits non-zero naming what is missing, rather
      than falling back to a stub. A stub judge that reached the real curve
      would be the one defect in this system that cannot be undone.

## 2. Generation goes through the product's path

Decided 10 Oct, after the questions in group 0: `agents.invoke` with the
`architect` role, the eval prompt as the task, the brain at the pinned commit as
the context. See the proposal; the alternative measured a harness.

- [x] 2.1 `AgentTurn` carries `model_call_id`, read from the completion the turn
      already holds. The only file in this change outside `evals`.
- [x] 2.2 The command resolves the `architect` prompt through the roster, so the
      agent is registered and its `prompt_sha` recorded — registration refuses a
      file whose content no longer matches what was recorded, and that refusal
      is what makes the version meaningful.
- [x] 2.3 The eval role is configuration, not a literal in `evals`. A role name
      is not a model identifier, but which role is measured is a deployment
      decision like the judge is.

## 3. The prompt stops being an unpinned confound

- [x] 3.1 `RunSummary` carries the distinct agent prompt versions behind a run,
      read through `model_call_id` → `agent_invocations` → `agents`. No
      migration: every link exists.
- [x] 3.2 The curve refuses when they differ, naming both. Absent on both sides
      compares equal — generating without an agent is a legitimate shape, and
      what is refused is a change between the runs.
- [x] 3.3 A test per direction: two runs differing **only** in prompt version
      are refused; the same prompt on both sides compares. The second half is
      what catches a refusal firing for the wrong reason.
- [x] 3.4 One mutation: the prompt refusal removed, the gate named.

## 4. Tests

- [x] 4.1 `main(["score", ...])` against a temporary database over the stub
      endpoint, asserting the run is scored and the judge recorded by name.
- [x] 4.2 Missing configuration exits non-zero and writes no `eval_results` row.
- [x] 4.3 The synthetic flag set makes the command refuse to touch a real run,
      proved against the existing guard rather than re-implemented.

## 5. The record

- [x] 5.1 An ADR superseding **ADR 0006's eval-judge clause alone**, recording
      that ADR 0010 made a cloud judge impermissible on 2 Sep and that the
      clause has been dead since. The rest of 0006's bindings stand and 0006 is
      not edited. Reaffirm 0010 explicitly: moving the judge to a remote
      provider needs 0010 superseded with an argument, not a flag.
- [x] 5.2 Record the five-week disagreement as the finding it is — two accepted
      ADRs in force and contradicting each other, surviving because nothing had
      ever been scored, so the dead clause was never executed and never failed.
      It belongs in the ADR's own Context, where the next reader of 0006 will
      follow the supersession link to it.
- [x] 5.3 `docs/MODELS.md`'s "frontier turns, eval judge" row tabulates the
      retired clause. It is where a reader picks the dead binding back up.
- [x] 5.4 `docs/SPEC_ROADMAP.md`'s `eval-scoring` row says what is left needs
      Token Factory. It is now false, and it is the sentence somebody reads when
      deciding whether a machine session can close the week-8 run.

## 6. Gate

- [x] 6.1 `python3 scripts/gate.py` green, run unpiped.
