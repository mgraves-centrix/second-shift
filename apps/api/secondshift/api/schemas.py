"""Request and response shapes for capture.

The client owns identity and time. It generates the ULID and records the capture
instant before any network call, so a queued entry is already complete when it
drains — which is what lets the server treat a replay as a lookup rather than a
merge.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class CaptureRequest(BaseModel):
    """An entry as the client recorded it.

    There is deliberately no `is_synthetic` field. Whether an entry is synthetic
    is the server's determination from its deployment; accepting it from a
    request would let a real dogfooding entry be excluded from every measurement,
    unrecoverably.
    """

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=26, max_length=26, description="Client ULID")
    created_at_ms: int = Field(gt=0, description="Client capture instant, authoritative")
    captured_tz: str = Field(min_length=1, description="IANA zone at capture")
    tz_offset_min: int = Field(ge=-900, le=900)
    policy: str
    text: str
    modality: str = "text"
    title: str | None = None
    source_device: str | None = None
    lat: float | None = Field(default=None, ge=-90, le=90)
    lon: float | None = Field(default=None, ge=-180, le=180)
    capture_profile: str | None = Field(
        default=None,
        description=(
            "Profile the client was told about when it captured. For a queue "
            "drained later this differs from the server's profile now, and the "
            "client's is the true one."
        ),
    )


class EntryResponse(BaseModel):
    id: str
    created_at_ms: int
    received_at_ms: int | None
    captured_tz: str
    policy: str
    status: str
    title: str | None
    text: str | None
    duplicate: bool = Field(
        default=False, description="True when this replayed an entry already stored"
    )


class PolicyAvailabilityResponse(BaseModel):
    policy: str
    available: bool
    reason: str | None = None


class CapabilityResponse(BaseModel):
    """Every policy, marked. Unavailable ones are never omitted.

    A filtered list of selectable options would hide that the Airlock exists —
    which matters most on the judge deployment, where the cloud profile cannot
    honor local-only at all.
    """

    profile: str
    degraded: bool
    degradation_reason: str | None = None
    policies: list[PolicyAvailabilityResponse]

    #: Whether this deployment serves a generated persona.
    #:
    #: Server-derived and never accepted from a request. A dense, plausible night
    #: is indistinguishable from a real one by eye, so the deployment says which
    #: it is and every surface can label it — otherwise seeded work is read as
    #: evidence of real use, which is the one claim a demonstration must not make.
    is_synthetic: bool = False
