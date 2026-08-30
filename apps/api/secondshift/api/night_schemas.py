"""The night view's read contract.

Written before either side of it, because the response shape is the only thing
the routes and the timeline need to agree on. Everything else about them is
independent.

Two properties this contract exists to hold:

Drawing a frame uses scalar fields only. `TimelineEvent` carries no payload —
detail is a separate request for one event — so a dense night renders without
parsing JSON, which the telemetry spec requires.

Times are absolute epoch milliseconds, and the offset that frames them travels
beside them rather than being resolved by the reader. A viewer in another
timezone must see the night as it happened where it happened, and the deferred
celestial layer needs an absolute instant and a position, not a fraction.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class TimelineEvent(BaseModel):
    """One row on the timeline. Scalar by design.

    `duration_ms` decides the mark: present renders as a bar, absent as a tick.
    That distinction separates a forty-second crawl from an instantaneous write
    and must survive without reading a label.
    """

    id: int
    ts_ms: int
    lane: str
    kind: str
    label: str
    severity: str
    duration_ms: int | None = None
    agent_invocation_id: str | None = None
    model_call_id: str | None = Field(
        default=None, description="Present when a model call produced this event"
    )
    is_synthetic: bool


class TimelinePage(BaseModel):
    """A window of events, with the cursor to continue from.

    The cursor is a timestamp and an identifier together. The identifier alone is
    not monotonic in time — nested work is recorded after its siblings and occurs
    before them — so paging on it silently reorders the night.
    """

    events: list[TimelineEvent]
    next_ts_ms: int | None = None
    next_id: int | None = None


class TimelineBucket(BaseModel):
    """Events aggregated for a zoomed-out view.

    `severity` is the strongest present, never an average: one error among forty
    routine rows has to survive being zoomed out, or the view hides the thing
    someone is looking for.
    """

    lane: str
    bucket_start_ms: int
    count: int
    severity: str


class Lane(BaseModel):
    """A row on the timeline, from the run as a whole.

    Sent as a roster rather than derived from the loaded window: two agent roles
    take a single invocation each across a whole night, so lanes built from
    what is on screen appear and vanish while scrubbing.
    """

    lane: str
    role: str | None = None
    invocations: int


class Stage(BaseModel):
    """A stage band. `ended_at_ms` is absent while a stage is still running."""

    stage: str
    seq: int
    status: str
    started_at_ms: int | None = None
    ended_at_ms: int | None = None


class Capture(BaseModel):
    """An idea captured before the run, for the gutter beside the axis."""

    id: str
    created_at_ms: int
    title: str | None = None
    policy: str


class Spend(BaseModel):
    """What a night cost, summed from recorded calls.

    Not from the rollup views: they exclude generated rows, so a wholly synthetic
    deployment renders blank from them — on the one instance that exists to be
    looked at. `generated` says whether these figures came from seeded work, so
    a demonstration can label them rather than present them as real spend.
    """

    spend_usd: float
    total_tokens: int
    cloud_tokens: int
    calls: int
    generated: bool


class ModelCallDetail(BaseModel):
    """The call behind an event. Fetched for one event, never to draw a frame."""

    id: str
    provider: str
    model: str
    model_version: str | None = None
    effort: str | None = None
    prompt_tokens: int
    completion_tokens: int
    reasoning_tokens: int
    total_tokens: int
    latency_ms: int | None = None
    estimated_cost_usd: float
    cache_hit: bool
    policy: str
    redaction_applied: bool


class EventDetail(BaseModel):
    """One event with what produced it.

    Deliberately excludes stored prompt and completion text. Those hold raw
    unredacted content for local-only ideas and must never reach a client — the
    obvious next hover affordance is the one that crosses the airlock.
    """

    event: TimelineEvent
    payload_json: str | None = None
    model_call: ModelCallDetail | None = None


class RunSummary(BaseModel):
    """A run in a list."""

    id: str
    night_of: str
    started_at_ms: int
    ended_at_ms: int | None = None
    outcome: str | None = None
    effective_policy: str
    is_synthetic: bool


class RunDetail(BaseModel):
    """A run with everything the axis needs to frame itself.

    `tz_offset_min` is the offset recorded at capture, not one resolved from the
    zone name now — resolving later gives the wrong hour for half the year, which
    is why the offset is stored in the first place.

    `extent_end_ms` includes the duration of every bar. Work near the end of a
    night runs past the last recorded instant, by over an hour in a generated
    night, and an axis ending at the last timestamp clips it.
    """

    id: str
    entry_id: str
    night_of: str
    started_at_ms: int
    ended_at_ms: int | None = None
    outcome: str | None = None
    furthest_stage: str | None = None
    effective_policy: str
    policy_source: str
    compute_profile: str
    is_synthetic: bool

    captured_tz: str
    tz_offset_min: int
    lat: float | None = None
    lon: float | None = None
    entry_title: str | None = None

    extent_start_ms: int | None = None
    extent_end_ms: int | None = None

    lanes: list[Lane]
    stages: list[Stage]
    captures: list[Capture]
    spend: Spend
