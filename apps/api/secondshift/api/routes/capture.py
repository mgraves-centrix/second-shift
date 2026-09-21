"""Recording a captured idea.

Live and taking real ideas, which makes this the one route that must not break.
Everything about an entry is decided by the client before it is sent — the
identifier, the instant, the timezone, the policy. The server records what it
receives and adds only what the client cannot know: when it arrived, what it was
offered, and whether this deployment is synthetic.
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Response, status

from ...db.connection import now_ms
from ..context import Context, get_context
from ..location import home_location
from ..mappers import capability_payload, entry_response
from ..schemas import CaptureRequest, EntryResponse
from ..titles import derive_title

router = APIRouter()


@router.post("/entries", response_model=EntryResponse)
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
        return entry_response(existing, duplicate=True)

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
                capability_payload(ctx.report).model_dump()
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
    return entry_response(ctx.repo.get_entry(entry_id), duplicate=False)
