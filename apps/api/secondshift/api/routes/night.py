"""The night view's read routes.

Five routes over one run: the list, the framing, the events, the events
aggregated, and one event in full. They are separated the way the scrubber
loads them — a frame redraws from `TimelinePage` alone, and the detail of a
single event is a request nobody makes while dragging.

Every handler is a projection of a repository read onto the fixed contract in
`night_schemas`. The mapping is here rather than in the repository because it
is a presentation decision: severity, for instance, is aggregated as an integer
rank because SQLite has no maximum over strings in severity order, and that
rank is an artifact of the aggregate rather than something a client should
learn.
"""

from __future__ import annotations

import sqlite3
from collections import Counter
from collections.abc import Callable

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ...db.repository import Repository
from ..night_schemas import (
    Capture,
    EventDetail,
    Lane,
    ModelCallDetail,
    RunDetail,
    RunSummary,
    Spend,
    Stage,
    TimelineBucket,
    TimelineEvent,
    TimelinePage,
)

#: How many events one page carries when the client does not say. A generated
#: night runs to thousands of rows, and a route that returns all of them by
#: default makes the first paint wait on the last hour of the night.
DEFAULT_PAGE = 500
MAX_PAGE = 5000

#: The inverse of the ranking `timeline_buckets` aggregates with. It exists
#: only so a maximum can be taken, and stops at this boundary.
_SEVERITY_BY_RANK = {3: "error", 2: "warn", 1: "info", 0: "debug"}

#: One event with its stored payload. `model_call_payloads` is deliberately
#: absent and must stay absent: it holds raw prompt and completion text for
#: local-only ideas, so joining it here would send them across the airlock in
#: service of a hover.
_EVENT_SQL = (
    "SELECT id, ts_ms, lane, kind, label, severity, duration_ms, "
    "agent_invocation_id, model_call_id, is_synthetic, payload_json "
    "FROM events WHERE id = ?"
)


def _event(row: sqlite3.Row) -> TimelineEvent:
    return TimelineEvent(
        id=row["id"],
        ts_ms=row["ts_ms"],
        lane=row["lane"],
        kind=row["kind"],
        label=row["label"],
        severity=row["severity"],
        duration_ms=row["duration_ms"],
        agent_invocation_id=row["agent_invocation_id"],
        model_call_id=row["model_call_id"],
        is_synthetic=bool(row["is_synthetic"]),
    )


def _summary(row: sqlite3.Row) -> RunSummary:
    return RunSummary(
        id=row["id"],
        night_of=row["night_of"],
        started_at_ms=row["started_at_ms"],
        ended_at_ms=row["ended_at_ms"],
        outcome=row["outcome"],
        effective_policy=row["effective_policy"],
        is_synthetic=bool(row["is_synthetic"]),
    )


def _lanes(repo: Repository, run_id: str) -> list[Lane]:
    """The roster, with each lane's invocation count against it.

    An invocation's lane is its agent's role and `events.lane` records that same
    string, which is the only thing joining the two reads. The roster leads
    because it is the authority on which rows exist: a lane carrying stage
    boundaries has no agent behind it at all, and building the list from
    invocations would drop it.
    """
    counts: Counter[str] = Counter(inv["role"] for inv in repo.invocation_tree(run_id))
    return [
        Lane(
            lane=lane,
            role=lane if lane in counts else None,
            invocations=counts.get(lane, 0),
        )
        for lane in repo.lane_roster(run_id)
    ]


def _spend(row: sqlite3.Row) -> Spend:
    return Spend(
        spend_usd=row["spend_usd"],
        total_tokens=row["total_tokens"],
        cloud_tokens=row["cloud_tokens"],
        calls=row["calls"],
        # A maximum over no rows is null, which describes a run that made no
        # calls rather than a run whose calls were real.
        generated=bool(row["any_synthetic"]),
    )


def _model_call(row: sqlite3.Row) -> ModelCallDetail:
    return ModelCallDetail(
        id=row["id"],
        provider=row["provider"],
        model=row["model"],
        model_version=row["model_version"],
        effort=row["effort"],
        prompt_tokens=row["prompt_tokens"],
        completion_tokens=row["completion_tokens"],
        reasoning_tokens=row["reasoning_tokens"],
        total_tokens=row["total_tokens"],
        latency_ms=row["latency_ms"],
        estimated_cost_usd=row["estimated_cost_usd"],
        cache_hit=bool(row["cache_hit"]),
        policy=row["policy"],
        redaction_applied=bool(row["redaction_applied"]),
    )


def night_router(get_repo: Callable[[], Repository]) -> APIRouter:
    """Build the read routes over whichever repository the app resolved."""
    router = APIRouter()

    def _require_run(repo: Repository, run_id: str) -> sqlite3.Row:
        row = repo.run_detail(run_id)
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"unknown run {run_id!r}",
            )
        return row

    @router.get("/runs", response_model=list[RunSummary])
    def runs(
        night_of: str | None = None,
        limit: int = Query(default=50, ge=1, le=500),
        repo: Repository = Depends(get_repo),
    ) -> list[RunSummary]:
        """Runs for a night, or the most recent runs when no night is named.

        The night is optional because the view opens before anyone has chosen a
        date. Requiring one means the first request a fresh client can make is
        one it has no way to construct.

        Ordering differs by intent: a named night reads forward in time, because
        it is being read as a sequence, while an unnamed request is answering
        "what happened last" and reads newest first.
        """
        if night_of is not None:
            return [_summary(r) for r in repo.runs_for_night(night_of)]
        return [_summary(r) for r in repo.recent_runs(limit)]

    @router.get("/runs/{run_id}", response_model=RunDetail)
    def run(run_id: str, repo: Repository = Depends(get_repo)) -> RunDetail:
        row = _require_run(repo, run_id)
        extent = repo.timeline_extent(run_id)
        return RunDetail(
            id=row["id"],
            entry_id=row["entry_id"],
            night_of=row["night_of"],
            started_at_ms=row["started_at_ms"],
            ended_at_ms=row["ended_at_ms"],
            outcome=row["outcome"],
            furthest_stage=row["furthest_stage"],
            effective_policy=row["effective_policy"],
            policy_source=row["policy_source"],
            compute_profile=row["compute_profile"],
            is_synthetic=bool(row["is_synthetic"]),
            captured_tz=row["captured_tz"],
            tz_offset_min=row["tz_offset_min"],
            lat=row["lat"],
            lon=row["lon"],
            entry_title=row["entry_title"],
            # A run that recorded nothing has no span. Reporting zeros would
            # hand the axis a night beginning in 1970.
            extent_start_ms=None if extent is None else extent[0],
            extent_end_ms=None if extent is None else extent[1],
            lanes=_lanes(repo, run_id),
            stages=[
                Stage(
                    stage=s["stage"],
                    seq=s["seq"],
                    status=s["status"],
                    started_at_ms=s["started_at_ms"],
                    ended_at_ms=s["ended_at_ms"],
                )
                for s in repo.run_stages(run_id)
            ],
            captures=[
                Capture(
                    id=c["id"],
                    created_at_ms=c["created_at_ms"],
                    title=c["title"],
                    policy=c["default_policy"],
                )
                for c in repo.captures_before_run(run_id)
            ],
            spend=_spend(repo.run_spend(run_id)),
        )

    @router.get("/runs/{run_id}/timeline", response_model=TimelinePage)
    def timeline(
        run_id: str,
        from_ms: int | None = None,
        to_ms: int | None = None,
        limit: int = Query(default=DEFAULT_PAGE, ge=1, le=MAX_PAGE),
        after_ts_ms: int | None = None,
        after_id: int | None = None,
        repo: Repository = Depends(get_repo),
    ) -> TimelinePage:
        _require_run(repo, run_id)
        if (after_ts_ms is None) != (after_id is None):
            # Half a cursor names no position. Accepting one alone would page
            # from an instant regardless of which rows at it were already sent,
            # which repeats or drops every row sharing that millisecond.
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=(
                    "after_ts_ms and after_id are one cursor; "
                    "supply both or neither"
                ),
            )
        after = None if after_ts_ms is None else (after_ts_ms, after_id)
        rows = repo.timeline(
            run_id, from_ms=from_ms, to_ms=to_ms, limit=limit, after=after
        )
        # A cursor only where the page filled: a short page is the end of the
        # window, and continuing from it would loop on the last row forever.
        more = len(rows) == limit
        return TimelinePage(
            events=[_event(r) for r in rows],
            next_ts_ms=rows[-1]["ts_ms"] if more else None,
            next_id=rows[-1]["id"] if more else None,
        )

    @router.get("/runs/{run_id}/timeline/buckets", response_model=list[TimelineBucket])
    def buckets(
        run_id: str,
        bucket_ms: int = Query(default=60_000, ge=1),
        repo: Repository = Depends(get_repo),
    ) -> list[TimelineBucket]:
        _require_run(repo, run_id)
        return [
            TimelineBucket(
                lane=b["lane"],
                bucket_start_ms=b["bucket_start_ms"],
                count=b["count"],
                severity=_SEVERITY_BY_RANK[b["severity_rank"]],
            )
            for b in repo.timeline_buckets(run_id, bucket_ms=bucket_ms)
        ]

    @router.get("/events/{event_id}", response_model=EventDetail)
    def event(event_id: int, repo: Repository = Depends(get_repo)) -> EventDetail:
        row = repo.connection.execute(_EVENT_SQL, (event_id,)).fetchone()
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"unknown event {event_id}",
            )
        call = repo.model_call_for_event(event_id)
        return EventDetail(
            event=_event(row),
            payload_json=row["payload_json"],
            model_call=None if call is None else _model_call(call),
        )

    return router
