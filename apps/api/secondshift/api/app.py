"""The capture API.

Two routes. `GET /capabilities` tells the surface which policies it may offer and
why any are unavailable; `POST /entries` records a captured idea.

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
    PolicyAvailabilityResponse,
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

    # Mounted last so every API route is matched first.
    if WEB_EXPORT.is_dir():
        app.mount("/", StaticFiles(directory=WEB_EXPORT, html=True), name="web")

    return app
