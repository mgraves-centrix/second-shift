"""Reading back what a night wrote.

`/events/{id}` is here rather than under a module of its own because it exists
to drill into a timeline and means nothing apart from one. The split between it
and the timeline is a contract rather than a convenience: the timeline response
has no field for an event payload, so a renderer cannot parse JSON to draw a
frame even by mistake.
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, status

from ..context import Context, get_context
from ..mappers import model_call, run_summary
from ..schemas import (
    EventDetailResponse,
    InvocationNodeResponse,
    RunStageResponse,
    RunSummaryResponse,
    TimelineEventResponse,
    TimelineResponse,
)

router = APIRouter()


@router.get("/runs", response_model=list[RunSummaryResponse])
def runs(ctx: Context = Depends(get_context)) -> list[RunSummaryResponse]:
    """Recorded nights, newest first.

    Synthetic runs are included and marked, not filtered. Rollups exclude
    them because they are measurements; a viewer is not a measurement, and
    hiding the only nights that exist would leave nothing to look at.
    """
    return [run_summary(r) for r in ctx.repo.list_runs()]


@router.get("/runs/{run_id}/timeline", response_model=TimelineResponse)
def timeline(run_id: str, ctx: Context = Depends(get_context)) -> TimelineResponse:
    """A whole night, in one response.

    Whole because a windowed query would put a fetch in the middle of a
    drag. At roughly a thousand events a night this is small; when it stops
    being small, the window is a rendering concern before it is a query one.
    """
    run = ctx.repo.run_summary(run_id)
    if run is None:
        # Refused rather than answered with an empty night, which would be
        # indistinguishable from a night in which nothing happened.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"unknown run {run_id!r}"
        )

    rows = ctx.repo.timeline(run_id)
    events = [
        TimelineEventResponse(
            id=r["id"],
            ts_ms=r["ts_ms"],
            lane=r["lane"],
            kind=r["kind"],
            label=r["label"],
            severity=r["severity"],
            duration_ms=r["duration_ms"],
            agent_invocation_id=r["agent_invocation_id"],
        )
        for r in rows
    ]
    # The lane an event recorded, never the role of whatever produced it: an
    # event may record a lane its producer's role does not match, and a
    # stage boundary has no producer at all.
    lanes = sorted({e.lane for e in events})

    return TimelineResponse(
        run=run_summary(run),
        # How far each stage got. `runs.outcome` is null on every recorded
        # run — nothing closes a run yet — so a night that stopped part-way
        # says so here or nowhere, and "no empty mornings" is a query over
        # exactly this table.
        stages=[
            RunStageResponse(
                stage=s["stage"],
                seq=s["seq"],
                status=s["status"],
                started_at_ms=s["started_at_ms"],
                ended_at_ms=s["ended_at_ms"],
            )
            for s in ctx.repo.stages_for_run(run_id)
        ],
        lanes=lanes,
        events=events,
        invocations=[
            InvocationNodeResponse(
                id=i["id"],
                parent_invocation_id=i["parent_invocation_id"],
                depth=i["depth"],
                stage=i["stage"],
                outcome=i["outcome"],
                started_at_ms=i["started_at_ms"],
                ended_at_ms=i["ended_at_ms"],
            )
            for i in ctx.repo.invocation_tree(run_id)
        ],
    )


@router.get("/events/{event_id}", response_model=EventDetailResponse)
def event_detail(
    event_id: int, ctx: Context = Depends(get_context)
) -> EventDetailResponse:
    """One event in full, for the one a person is looking at.

    Every model call its invocation made, rather than the one the event
    corresponds to: `events` carries no model call id, so a single answer
    would be adjacency presented as fact. An invocation makes one to three.
    """
    row = ctx.repo.get_event(event_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"unknown event {event_id}"
        )

    payload = None
    if row["payload_json"]:
        try:
            payload = json.loads(row["payload_json"])
        except json.JSONDecodeError:
            # Unreadable detail is reported as absent rather than failing the
            # request: the event itself is still worth showing.
            payload = None

    # Counts and costs only. `model_call_payloads` holds what was said, and
    # the constitution names an export path that includes it as a Privacy
    # Airlock violation — so it is not joined here and the response has no
    # field it could travel in.
    calls = (
        ctx.repo.model_calls_for_invocation(row["agent_invocation_id"])
        if row["agent_invocation_id"]
        else []
    )
    return EventDetailResponse(
        id=row["id"],
        run_id=row["run_id"],
        ts_ms=row["ts_ms"],
        lane=row["lane"],
        kind=row["kind"],
        label=row["label"],
        severity=row["severity"],
        duration_ms=row["duration_ms"],
        agent_invocation_id=row["agent_invocation_id"],
        payload=payload if isinstance(payload, dict) else None,
        model_calls=[model_call(c) for c in calls],
    )
