"""Request and response shapes for capture.

The client owns identity and time. It generates the ULID and records the capture
instant before any network call, so a queued entry is already complete when it
drains — which is what lets the server treat a replay as a lookup rather than a
merge.
"""

from __future__ import annotations

from typing import Literal

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


class RunSummaryResponse(BaseModel):
    """A recorded night, enough to pick one and know what it was.

    `is_synthetic` is carried rather than filtered. A generated night is the only
    kind that exists yet, so a view that hid them would be empty and unverifiable
    — but a screenshot of one must never be mistaken for evidence, so the client
    is told which it is looking at.
    """

    id: str
    night_of: str
    started_at_ms: int
    ended_at_ms: int | None
    effective_policy: str
    compute_profile: str
    outcome: str | None
    furthest_stage: str | None
    is_synthetic: bool
    #: The frame the night's events occupy. `last_event_end_ms` is the last
    #: event's END, not its start: the longest bar in a generated night begins
    #: 67 minutes before the last event starts, and a frame taken from the last
    #: start would draw it past the edge of its own night.
    first_event_ms: int | None
    last_event_end_ms: int | None
    event_count: int
    #: The zone the idea behind this night was captured in. The night renders in
    #: it rather than in the server's, because "the frantic bit at 3am" is a
    #: claim about where the person was. It is also everything the deferred
    #: celestial layer needs, which is why it is carried now rather than added
    #: when that lands.
    captured_tz: str | None
    tz_offset_min: int | None


class TimelineEventResponse(BaseModel):
    """One event, as a frame needs it.

    There is deliberately no payload field. "The renderer must never parse JSON
    to draw a frame" is a property, and a property the response shape cannot
    express is one the renderer cannot break. Detail is `GET /events/{id}`.
    """

    id: int
    ts_ms: int
    lane: str
    kind: str
    label: str
    severity: str
    duration_ms: int | None
    agent_invocation_id: str | None


class InvocationNodeResponse(BaseModel):
    """Parentage and depth. No role: `agent_invocations` does not carry one.

    A lane is `events.lane`, which is a rendering decision recorded at write
    time — not the role of whatever produced the event, which differs for some
    of them and does not exist for others.
    """

    id: str
    parent_invocation_id: str | None
    depth: int
    stage: str | None
    outcome: str | None
    started_at_ms: int
    ended_at_ms: int | None


class RunStageResponse(BaseModel):
    """How far one stage got.

    Carried because `runs.outcome` is null on every recorded run — nothing closes
    a run yet — and "no empty mornings" is a query over exactly this table. A
    night that stopped part-way says so here or nowhere.
    """

    stage: str
    seq: int
    status: str
    started_at_ms: int | None
    ended_at_ms: int | None


class TimelineResponse(BaseModel):
    """A whole night, in one response.

    Whole because a windowed query would put a fetch in the middle of a drag,
    and a scrubber with a loading state mid-drag is not a scrubber.
    """

    run: RunSummaryResponse
    stages: list[RunStageResponse]
    lanes: list[str]
    events: list[TimelineEventResponse]
    invocations: list[InvocationNodeResponse]


class ModelCallResponse(BaseModel):
    id: str
    ts_ms: int
    provider: str
    model: str
    policy: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    estimated_cost_usd: float | None
    latency_ms: int | None


class EventDetailResponse(BaseModel):
    """What one event carries, fetched for the one a person is looking at.

    Every model call the event's invocation made, rather than the one the event
    corresponds to: `events` records no model call id, so a single answer would
    be inferred from adjacency and presented as fact.

    There is deliberately no prompt or completion text. `model_call_payloads`
    holds what was said, and the constitution names an export path that includes
    it as a Privacy Airlock violation — so this response has no field it could
    travel in. Counts and costs are accounting; the words are not.
    """

    id: int
    run_id: str | None
    ts_ms: int
    lane: str
    kind: str
    label: str
    severity: str
    duration_ms: int | None
    agent_invocation_id: str | None
    payload: dict | None
    model_calls: list[ModelCallResponse]


class StageLineResponse(BaseModel):
    """One stage, as the morning reports it.

    `reason` is present for a failed stage and null for a skipped one, because
    `run_stages` has no reason column and the night persists only failures. A
    null here means "not recorded", never "no reason" — see
    `morning/briefing.py`.
    """

    stage: str
    status: str
    reason: str | None
    artifacts: list[str]


class NightLineResponse(BaseModel):
    run_id: str
    entry_id: str
    night_of: str
    outcome: str | None
    effective_policy: str
    stages: list[StageLineResponse]


class QuestionResponse(BaseModel):
    """One open decision.

    `will_leave_the_machine` travels with the question rather than being a
    screen's job to remember. A warning that lives only in a component is one
    the next component does not inherit.
    """

    decision_id: str
    entry_id: str
    question: str
    rationale: str | None
    blocking_stage: str | None
    will_leave_the_machine: bool


class BriefingResponse(BaseModel):
    """What the night did and what it could not decide.

    Deliberately not a chat transcript. `NOT_BUILDING.md` excludes a general
    chat interface by name, and the shape of this response is part of that
    boundary: nights and questions, no free-form turns.
    """

    nights: list[NightLineResponse]
    questions: list[QuestionResponse]
    interviewer_error: str | None


class AnswerRequest(BaseModel):
    """An answer to one question the system asked.

    There is no `message` field and no free-text instruction path. An answer is
    always *against a decision id*, which is the scope boundary made structural:
    an endpoint that accepted arbitrary text and routed it would be the chat
    interface the constitution excludes, under a different name.
    """

    answer: str
    status: Literal["decided", "deferred", "queued-for-tonight", "obsolete"]
    modality: Literal["text", "voice"] = "text"


class AnswerResponse(BaseModel):
    decision_id: str
    status: str
    answered_at_ms: int
