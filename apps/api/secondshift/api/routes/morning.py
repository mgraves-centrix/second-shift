"""The briefing, and answering one question it asked.

`/decisions/{id}/answer` is here rather than under a module of its own because
it is the interview's write side. The path carries the decision id, so there is
no route that takes an instruction with nowhere to attach it — the scope
boundary in the URL shape rather than in a rule somebody has to remember.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from ...morning import assemble
from ...morning.interview import answer
from ..context import Context, get_context
from ..schemas import (
    AnswerRequest,
    AnswerResponse,
    ArtifactRefResponse,
    BriefingResponse,
    NightLineResponse,
    QuestionResponse,
    StageLineResponse,
)

router = APIRouter()


@router.get("/morning", response_model=BriefingResponse)
def morning(ctx: Context = Depends(get_context)) -> BriefingResponse:
    """What the night did and what it could not decide.

    Covers every run since the last decision a person *acted* on. Fetching
    this does not advance that boundary — rendering a briefing is not the
    same as reading one, and a GET that consumed its own delta would lose a
    morning because somebody opened the app while walking.

    Assembled from rows with no model call, so a night that ran while the
    interviewer was down still reports what it produced. Principle 3.
    """
    briefing = assemble(ctx.repo, include_synthetic=ctx.is_synthetic)
    return BriefingResponse(
        nights=[
            NightLineResponse(
                run_id=n.run_id,
                entry_id=n.entry_id,
                night_of=n.night_of,
                outcome=n.outcome,
                effective_policy=n.effective_policy,
                stages=[
                    StageLineResponse(
                        stage=s.stage,
                        status=s.status,
                        reason=s.reason,
                        artifacts=[
                            ArtifactRefResponse(
                                artifact_id=a.artifact_id, path=a.path
                            )
                            for a in s.artifacts
                        ],
                    )
                    for s in n.stages
                ],
            )
            for n in briefing.nights
        ],
        questions=[
            QuestionResponse(
                decision_id=q.decision_id,
                entry_id=q.entry_id,
                question=q.question,
                rationale=q.rationale,
                blocking_stage=q.blocking_stage,
                will_leave_the_machine=q.will_leave_the_machine,
            )
            for q in briefing.questions
        ],
        interviewer_error=briefing.interviewer_error,
    )


@router.post("/decisions/{decision_id}/answer", response_model=AnswerResponse)
def answer_decision(
    decision_id: str,
    body: AnswerRequest,
    ctx: Context = Depends(get_context),
) -> AnswerResponse:
    """Answer one question the system asked.

    The path carries the decision id, so there is no route here that takes
    an instruction with nowhere to attach it. That is the scope boundary in
    the URL shape rather than in a rule somebody has to remember: a general
    chat interface is excluded by name, and this is how it stays excluded.
    """
    try:
        answer(
            ctx.repo,
            decision_id,
            text=body.answer,
            status=body.status,
            modality=body.modality,
        )
    except ValueError as exc:
        row = ctx.repo.connection.execute(
            "SELECT answer, status, answered_at_ms FROM decisions WHERE id = ?",
            (decision_id,),
        ).fetchone()
        if row is None:
            # An answer to a question nobody asked has nothing to mean.
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
            ) from exc
        if row["answer"] != body.answer or row["status"] != body.status:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"decision {decision_id!r} was already answered differently",
            ) from exc
        # The same answer again: a retry after a response that never
        # arrived. Refusing it told the screen the answer was not recorded,
        # and the person could not get past a question they had answered.
    else:
        row = ctx.repo.connection.execute(
            "SELECT status, answered_at_ms FROM decisions WHERE id = ?",
            (decision_id,),
        ).fetchone()
    return AnswerResponse(
        decision_id=decision_id,
        status=row["status"],
        answered_at_ms=row["answered_at_ms"],
    )
