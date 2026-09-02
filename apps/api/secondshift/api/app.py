"""The capture API, and the night it recorded.

`GET /capabilities` tells the surface which policies it may offer and why any are
unavailable; `POST /entries` records a captured idea. `GET /runs`,
`GET /runs/{id}/timeline` and `GET /events/{id}` read back what a night wrote.

The timeline routes are read-only, and the split between the last two is a
contract rather than a convenience: the timeline response has no field for an
event payload, so a renderer cannot parse JSON to draw a frame even by mistake.

Everything about an entry is decided by the client before it is sent — the
identifier, the instant, the timezone, the policy. The server records what it
receives and adds only what the client cannot know: when it arrived, what it was
offered, and whether this deployment is synthetic.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Response, status
from fastapi.staticfiles import StaticFiles

from ..airlock.capability import CapabilityReport, build_report
from ..config import ResolvedProfile, resolve_profile
from ..db.connection import connect, now_ms
from ..db.migrate import migrate
from ..db.repository import Repository
from ..telemetry.pricing import PricingTable
from ..telemetry.recorder import Recorder
from .location import home_location
from .schemas import (
    CapabilityResponse,
    CaptureRequest,
    EntryResponse,
    EventDetailResponse,
    InvocationNodeResponse,
    ModelCallResponse,
    PolicyAvailabilityResponse,
    RunStageResponse,
    RunSummaryResponse,
    TimelineEventResponse,
    TimelineResponse,
)
from .titles import derive_title


#: The exported PWA, when it has been built. Serving it from the API keeps the
#: capture app and its API on one origin — no CORS, no second process to be down
#: at 2am, and `NEXT_PUBLIC_API_BASE` can stay empty.
WEB_EXPORT = Path(__file__).resolve().parents[3] / "web" / "out"


@dataclass
class Context:
    """Everything a request handler needs, resolved once at startup."""

    repo: Repository
    recorder: Recorder
    profile: ResolvedProfile
    report: CapabilityReport
    is_synthetic: bool


def build_context(
    db_path: str,
    *,
    is_synthetic: bool = False,
    profile: ResolvedProfile | None = None,
) -> Context:
    conn = connect(db_path)
    migrate(conn)
    repo = Repository(conn)
    resolved = profile if profile is not None else resolve_profile()
    return Context(
        repo=repo,
        recorder=Recorder(
            repo, pricing=PricingTable.load(), compute_profile=str(resolved.profile)
        ),
        profile=resolved,
        report=build_report(resolved),
        is_synthetic=is_synthetic,
    )


def _capability_payload(report: CapabilityReport) -> CapabilityResponse:
    return CapabilityResponse(
        profile=str(report.profile),
        degraded=report.degraded,
        degradation_reason=report.degradation_reason,
        policies=[
            PolicyAvailabilityResponse(
                policy=str(a.policy), available=a.available, reason=a.reason
            )
            for a in report.policies
        ],
    )


def _run_summary(row: sqlite3.Row) -> RunSummaryResponse:
    keys = row.keys()
    return RunSummaryResponse(
        id=row["id"],
        night_of=row["night_of"],
        started_at_ms=row["started_at_ms"],
        ended_at_ms=row["ended_at_ms"],
        effective_policy=row["effective_policy"],
        compute_profile=row["compute_profile"],
        outcome=row["outcome"],
        furthest_stage=row["furthest_stage"],
        is_synthetic=bool(row["is_synthetic"]),
        # Present when the row came from `list_runs`, which computes the frame.
        first_event_ms=row["first_event_ms"] if "first_event_ms" in keys else None,
        last_event_end_ms=row["last_event_end_ms"] if "last_event_end_ms" in keys else None,
        event_count=row["event_count"] if "event_count" in keys else 0,
        captured_tz=row["captured_tz"] if "captured_tz" in keys else None,
        tz_offset_min=row["tz_offset_min"] if "tz_offset_min" in keys else None,
    )


def _model_call(row: sqlite3.Row) -> ModelCallResponse:
    return ModelCallResponse(
        id=row["id"],
        ts_ms=row["ts_ms"],
        provider=row["provider"],
        model=row["model"],
        policy=row["policy"],
        prompt_tokens=row["prompt_tokens"],
        completion_tokens=row["completion_tokens"],
        total_tokens=row["total_tokens"],
        estimated_cost_usd=row["estimated_cost_usd"],
        latency_ms=row["latency_ms"],
    )


def _entry_response(row: sqlite3.Row, *, duplicate: bool) -> EntryResponse:
    return EntryResponse(
        id=row["id"],
        created_at_ms=row["created_at_ms"],
        received_at_ms=row["received_at_ms"],
        captured_tz=row["captured_tz"],
        policy=row["default_policy"],
        status=row["status"],
        title=row["title"],
        text=row["raw_text"],
        duplicate=duplicate,
    )


def create_app(context: Context) -> FastAPI:
    app = FastAPI(title="Second Shift — capture", version="0.1.0")

    def get_context() -> Context:
        return context

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/capabilities", response_model=CapabilityResponse)
    def capabilities(ctx: Context = Depends(get_context)) -> CapabilityResponse:
        """Every policy with its availability and reason. None are omitted."""
        return _capability_payload(ctx.report)

    @app.post("/entries", response_model=EntryResponse)
    def capture(
        request: CaptureRequest,
        response: Response,
        ctx: Context = Depends(get_context),
    ) -> EntryResponse:
        existing = ctx.repo.get_entry(request.id)
        if existing is not None:
            # A replay. Idempotent and silent: not an error, not a second row,
            # and no failure recorded — routine client retries must not dominate
            # the failure ledger.
            if (existing["raw_text"] or "") != request.text:
                ctx.recorder.record_event(
                    lane="capture",
                    kind="note",
                    label="replay with divergent content; stored version kept",
                    entry_id=request.id,
                    severity="warn",
                    is_synthetic=ctx.is_synthetic,
                )
            response.status_code = status.HTTP_200_OK
            return _entry_response(existing, duplicate=True)

        try:
            ctx.report.for_policy(request.policy)
        except KeyError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"unknown policy {request.policy!r}",
            ) from None

        home = home_location()
        try:
            entry_id = ctx.recorder.record_entry(
                created_at_ms=request.created_at_ms,
                received_at_ms=now_ms(),
                captured_tz=request.captured_tz,
                tz_offset_min=request.tz_offset_min,
                modality=request.modality,
                # Policy is recorded as INTENT. It is never filtered by what the
                # current profile can honor; a policy the profile cannot honor is a
                # quarantine decision made later, not a capture-time rewrite.
                default_policy=request.policy,
                status="queued",
                capture_profile=request.capture_profile or str(ctx.profile.profile),
                raw_text=request.text,
                title=request.title or derive_title(request.text),
                source_device=request.source_device,
                lat=request.lat if request.lat is not None else home.lat,
                lon=request.lon if request.lon is not None else home.lon,
                offered_capability_json=json.dumps(
                    _capability_payload(ctx.report).model_dump()
                ),
                entry_id=request.id,
                is_synthetic=ctx.is_synthetic,
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
            ) from exc

        ctx.recorder.record_event(
            lane="capture",
            kind="note",
            label=f"captured under {request.policy}",
            entry_id=entry_id,
            is_synthetic=ctx.is_synthetic,
        )
        response.status_code = status.HTTP_201_CREATED
        return _entry_response(ctx.repo.get_entry(entry_id), duplicate=False)

    @app.get("/runs", response_model=list[RunSummaryResponse])
    def runs(ctx: Context = Depends(get_context)) -> list[RunSummaryResponse]:
        """Recorded nights, newest first.

        Synthetic runs are included and marked, not filtered. Rollups exclude
        them because they are measurements; a viewer is not a measurement, and
        hiding the only nights that exist would leave nothing to look at.
        """
        return [_run_summary(r) for r in ctx.repo.list_runs()]

    @app.get("/runs/{run_id}/timeline", response_model=TimelineResponse)
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
            run=_run_summary(run),
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

    @app.get("/events/{event_id}", response_model=EventDetailResponse)
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
            model_calls=[_model_call(c) for c in calls],
        )

    # Mounted last so every API route is matched first.
    if WEB_EXPORT.is_dir():
        app.mount("/", StaticFiles(directory=WEB_EXPORT, html=True), name="web")

    return app
