"""One complete synthetic night, written through the repository layer.

Everything derives from a single seeded generator, identifiers included, so the
same seed writes the same night into any empty database. That is what makes a
demo rehearsable and lets a test assert on a specific row rather than on a
shape.

Every row that can carry `is_synthetic` carries it set. The rollup views already
exclude those, so a generated night renders and does not count — the property
that lets it share a database with real work instead of needing one of its own.

Writes go through `Repository`, never raw SQL, so a night this produces is a
night the system could actually have produced: the airlock CHECK, the entry
status machine and the foreign keys all apply on the way in. A generator that
reached past them would happily emit nights that cannot exist, and the mistake
would surface weeks later, in whatever had been built against them.
"""

from __future__ import annotations

import datetime as dt
import json
import random
from dataclasses import dataclass

from secondshift.airlock.policy import (
    Policy,
    PolicySource,
    Provider,
    assert_permitted,
    is_remote,
)
from secondshift.db.connection import transaction
from secondshift.db.repository import Repository
from secondshift.telemetry.failures import (
    BadOutput,
    ToolQuotaExceeded,
    classify,
    signature,
)

from .content import IDEAS, RESOLUTIONS, STAGE_WORK, SYNTHETIC, TOPICS, output_path
from .ids import Mint

#: The local date a generated night belongs to. Fixed rather than derived from
#: today: a seed that produced a different night each day would not be a seed.
DEFAULT_NIGHT_OF = "2026-08-27"

MS_PER_HOUR = 3_600_000

#: The local clock a night runs on. Capture happens through the evening; the run
#: starts once the machine is free and is still going when the morning arrives.
CAPTURE_FROM_HOUR = 17
NIGHT_START_HOUR = 22
NIGHT_HOURS = 7

LOCAL = str(Provider.LOCAL_VLLM)
HOSTED = str(Provider.TOKEN_FACTORY)
BATCH = str(Provider.NEBIUS_JOB)

#: In schema order, which is also the order a night executes them in.
STAGES: tuple[str, ...] = (
    "brief",
    "research",
    "mockups",
    "build",
    "critique",
    "distill",
)

#: The lead role for each stage and the roles it delegates to. Distinct roles
#: per stage are what give the timeline distinct lanes; a tree built from a
#: single role renders as one band and proves nothing about the layout.
_STAGE_ROLES: dict[str, tuple[str, tuple[str, ...]]] = {
    "brief": ("interviewer", ("researcher", "distiller")),
    "research": ("researcher", ("researcher", "critic")),
    "mockups": ("architect", ("builder", "critic")),
    "build": ("builder", ("builder", "critic")),
    "critique": ("critic", ("critic", "distiller")),
    "distill": ("distiller", ("distiller", "critic")),
}

#: The event kind a stage's work reads as, so every lane has a characteristic
#: mark rather than an undifferentiated stream of notes.
_STAGE_ACTIVITY: dict[str, str] = {
    "brief": "note",
    "research": "search",
    "mockups": "file_write",
    "build": "file_write",
    "critique": "note",
    "distill": "file_write",
}

#: Children spawned at depth 1, 2 and 3. The minimums are what make the night
#: dense by construction: six stages of at least twenty-one invocations, each
#: emitting at least four events, clears the four-hundred-event floor on every
#: seed rather than on most of them. A night that is only usually dense enough
#: is a night the scrubber can only usually be built against.
_FANOUT: tuple[tuple[int, int], ...] = ((4, 5), (2, 3), (1, 2))

#: How much of its parent's window a child occupies. Below one, so a child
#: always closes before its parent; well below one, so siblings overlap the way
#: agents dispatched together actually do.
_CHILD_SHARE = (0.35, 0.70)

#: Models named generically. A seed must not write a real model identifier into
#: rows a judge reads: it would claim a binding the deployment may not have, and
#: which backend serves a role is configuration rather than data.
_MODELS: dict[str, tuple[str, ...]] = {
    LOCAL: ("local-reasoner", "local-reasoner-lite"),
    HOSTED: ("hosted-reasoner", "hosted-reasoner-mini"),
    BATCH: ("batch-builder",),
}

#: USD per million tokens, prompt then completion. Deliberately not read from
#: `config/pricing.toml`: that table prices only the models this project
#: actually runs, so it raises `MissingRate` for a generic name — and a
#: generator that cannot price a call cannot fill the cost curve it exists to
#: populate. Local inference is metered at zero for the reason the real table
#: gives: the electricity is not billed per token.
_RATES_USD_PER_MTOK: dict[str, tuple[float, float]] = {
    LOCAL: (0.0, 0.0),
    HOSTED: (0.60, 1.80),
    BATCH: (0.35, 1.05),
}

#: IANA zone with its offset in August 2026. Both are carried because the schema
#: stores both: the offset at the capture instant is what renders, and resolving
#: a zone at read time would give the wrong hour for half the year.
_ZONES: tuple[tuple[str, int], ...] = (
    ("America/Los_Angeles", -420),
    ("America/New_York", -240),
    ("Europe/Lisbon", 60),
    ("Asia/Tokyo", 540),
)

_DEVICES: tuple[str, ...] = ("synthetic-phone", "synthetic-laptop")

#: Failures are put through `telemetry.failures.classify` rather than typed by
#: hand, so a seeded failure carries the taxonomy entry and the normalized
#: signature a real one would. A ledger view built against these groups real
#: failures correctly on the first night that produces one.
_FAILURE_TEMPLATES: tuple[tuple[type[BaseException], str], ...] = (
    (RuntimeError, "CUDA out of memory allocating the synthetic working set"),
    (TimeoutError, "synthetic completion timed out waiting on the reasoner"),
    (ConnectionError, "connection refused reaching the synthetic search endpoint"),
    (RuntimeError, "build failed: no matching distribution for a synthetic wheel"),
    (BadOutput, "critique rejected the synthetic draft as unsupported"),
    (ToolQuotaExceeded, "search credits exhausted partway through the synthetic night"),
    (RuntimeError, "the synthetic orchestrator step raised before checkpointing"),
)

_FAILURES_PER_NIGHT = (6, 10)


@dataclass(frozen=True, slots=True)
class _Span:
    """A window of the night, in epoch milliseconds."""

    start_ms: int
    end_ms: int

    @property
    def duration_ms(self) -> int:
        return self.end_ms - self.start_ms

    def within(self, rng: random.Random, share: float) -> _Span:
        """A sub-window covering `share` of this one, placed at random inside it."""
        length = int(self.duration_ms * share)
        offset = rng.randrange(max(1, self.duration_ms - length))
        return _Span(self.start_ms + offset, self.start_ms + offset + length)

    def instants(self, rng: random.Random, count: int) -> list[int]:
        """`count` instants inside the window, in order."""
        return sorted(rng.randrange(self.start_ms, self.end_ms) for _ in range(count))


@dataclass(frozen=True, slots=True)
class _Invocation:
    """One node of the tree, held while its outcome is still undecided."""

    invocation_id: str
    parent_id: str | None
    stage: str
    role: str
    span: _Span


@dataclass(frozen=True, slots=True)
class GeneratedNight:
    """What one call wrote, so a caller can name a row instead of hunting for it."""

    run_id: str
    subject_entry_id: str
    entry_ids: tuple[str, ...]
    invocation_ids: tuple[str, ...]
    failure_ids: tuple[str, ...]
    model_call_ids: tuple[str, ...]
    tool_call_ids: tuple[str, ...]
    artifact_ids: tuple[str, ...]
    variant_group: str
    event_count: int
    started_at_ms: int
    ended_at_ms: int
    policy: str


def generate_night(
    repo: Repository,
    *,
    seed: int,
    night_of: str = DEFAULT_NIGHT_OF,
    policy: str = str(Policy.CLOUD_ASSISTED),
    compute_profile: str = "spark",
) -> GeneratedNight:
    """Write one synthetic night and return what it wrote.

    The night lands in a single transaction. A half-written night is worse than
    none: it renders as a run that stopped for no recorded reason, and the
    reason would be this generator rather than anything the system did.
    """
    generator = _Generator(
        repo,
        seed=seed,
        night_of=night_of,
        policy=policy,
        compute_profile=compute_profile,
    )
    with transaction(repo.connection):
        return generator.write()


class _Generator:
    """The night's state while it is being written.

    A class rather than free functions because nearly every step needs the same
    five things — the seeded generator, the mint, the run, the policy, the clock
    — and threading those through twenty parameters buries the shape of the
    night, which is the part worth reading.
    """

    def __init__(
        self,
        repo: Repository,
        *,
        seed: int,
        night_of: str,
        policy: str,
        compute_profile: str,
    ) -> None:
        self._repo = repo
        self._rng = random.Random(seed)
        self._mint = Mint(self._rng)
        self._night_of = night_of
        self._policy = policy
        self._profile = compute_profile

        self._zone, self._offset_min = self._rng.choice(_ZONES)
        self._tz = dt.timezone(dt.timedelta(minutes=self._offset_min))
        self._night = self._night_span()

        self._agents: dict[str, str] = {}
        self._invocations: list[_Invocation] = []
        self._model_calls: list[str] = []
        self._tool_calls: list[str] = []
        self._events = 0
        self._run_id = ""
        # One group ties the build fan-out together. Minted from the seeded
        # generator like everything else, so two runs of the same seed produce
        # the same grouping.
        self._variant_group = self._mint(self._night.start_ms)

    # -- the clock ---------------------------------------------------------

    def _local(self, hour: int) -> int:
        """An instant on the night's own local evening, as epoch milliseconds."""
        day = dt.date.fromisoformat(self._night_of)
        moment = dt.datetime(day.year, day.month, day.day, hour, tzinfo=self._tz)
        return int(moment.timestamp() * 1000)

    def _night_span(self) -> _Span:
        start = self._local(NIGHT_START_HOUR) + self._rng.randrange(20 * 60_000)
        end = start + NIGHT_HOURS * MS_PER_HOUR + self._rng.randrange(40 * 60_000)
        return _Span(start, end)

    def _stage_windows(self) -> dict[str, _Span]:
        """Contiguous, unequal windows covering the night.

        Unequal because stages are: research reads for an hour and distillation
        takes ten minutes. Even windows would give the timeline a regularity no
        real night has, and a scrubber tuned to that regularity would look wrong
        on the first real one it rendered.
        """
        weights = [self._rng.uniform(0.6, 1.6) for _ in STAGES]
        total = sum(weights)
        windows: dict[str, _Span] = {}
        cursor = self._night.start_ms
        for stage, weight in zip(STAGES, weights, strict=True):
            width = int(self._night.duration_ms * weight / total)
            windows[stage] = _Span(cursor, cursor + width)
            cursor += width
        return windows

    # -- the night ---------------------------------------------------------

    def write(self) -> GeneratedNight:
        entries = self._capture()
        subject = entries[0]
        self._run_id = self._open_run(subject)

        windows = self._stage_windows()
        self._stages(windows)
        for stage, window in windows.items():
            lead, _ = _STAGE_ROLES[stage]
            self._spawn(stage=stage, role=lead, span=window, parent=None, depth=0)

        artifacts = self._artifacts(subject)
        failures = self._failures()
        self._close_invocations(failed={invocation for invocation, _ in failures})
        self._repo.transition_entry(subject, to_status="answered")

        return GeneratedNight(
            run_id=self._run_id,
            subject_entry_id=subject,
            entry_ids=tuple(entries),
            invocation_ids=tuple(i.invocation_id for i in self._invocations),
            failure_ids=tuple(failure for _, failure in failures),
            model_call_ids=tuple(self._model_calls),
            tool_call_ids=tuple(self._tool_calls),
            artifact_ids=tuple(artifacts),
            variant_group=self._variant_group,
            event_count=self._events,
            started_at_ms=self._night.start_ms,
            ended_at_ms=self._night.end_ms,
            policy=self._policy,
        )

    # -- artifacts ---------------------------------------------------------

    def _content_sha(self) -> str:
        """A plausible content hash from the seeded generator.

        Not a hash of anything: these artifacts have no bytes behind them. It is
        shaped like a real one so a renderer that displays it has something of
        the right length to display, and it is reproducible like everything else.
        """
        return "".join(self._rng.choice("0123456789abcdef") for _ in range(40))

    def _artifacts(self, entry_id: str) -> list[str]:
        """The night's output, including the build fan-out.

        The variants are the point. A build that fanned out to several parallel
        jobs and was then ranked by the critic is the argument for using a cloud
        executor at all, and it is unreadable unless the artifacts carry both the
        group that ties them together and the rank that orders them.

        Ranks are a shuffled permutation rather than the generation order, so a
        renderer that quietly assumes rank equals index is wrong on this data —
        which is the point of generating it.
        """
        written: list[str] = []
        builders = [i for i in self._invocations if i.stage == "build"] or self._invocations

        for stage, kind in (("brief", "brief"), ("research", "research_digest")):
            window = self._stage_windows()[stage]
            producer = next(
                (i for i in self._invocations if i.stage == stage), self._invocations[0]
            )
            written.append(
                self._repo.insert_artifact(
                    run_id=self._run_id,
                    entry_id=entry_id,
                    stage=stage,
                    kind=kind,
                    path=f"artifacts/{self._night_of}/{kind}.md",
                    created_at_ms=window.end_ms,
                    produced_by_invocation_id=producer.invocation_id,
                    artifact_id=self._mint(window.end_ms),
                    content_sha=self._content_sha(),
                    artifact_bytes=self._rng.randint(1_200, 9_000),
                    is_synthetic=True,
                )
            )

        window = self._stage_windows()["build"]
        count = self._rng.randint(3, 5)
        ranks = list(range(1, count + 1))
        self._rng.shuffle(ranks)
        for index, rank in enumerate(ranks):
            producer = builders[index % len(builders)]
            written.append(
                self._repo.insert_artifact(
                    run_id=self._run_id,
                    entry_id=entry_id,
                    stage="build",
                    kind="build",
                    path=f"artifacts/{self._night_of}/build-{index}/index.html",
                    variant_group=self._variant_group,
                    variant_index=index,
                    variant_rank=rank,
                    created_at_ms=window.end_ms,
                    produced_by_invocation_id=producer.invocation_id,
                    artifact_id=self._mint(window.end_ms),
                    content_sha=self._content_sha(),
                    artifact_bytes=self._rng.randint(4_000, 60_000),
                    is_synthetic=True,
                )
            )
        return written

    # -- capture -----------------------------------------------------------

    def _capture(self) -> list[str]:
        """The evening's captures, the first of which the night runs on.

        Written captured-then-transitioned rather than inserted at their final
        status, so a generated queue reaches that status by the route a real one
        takes. An entry that arrived at `queued` by a path no real entry can
        follow is precisely the row that renders now and cannot be reproduced
        later.
        """
        count = self._rng.randint(5, 9)
        ideas = self._rng.sample(IDEAS, count)
        window = _Span(self._local(CAPTURE_FROM_HOUR), self._night.start_ms)
        instants = window.instants(self._rng, count)

        ids: list[str] = []
        for index, idea in enumerate(ideas):
            title, text = idea
            created = instants[index]
            entry_id = self._mint(created)
            voice = self._rng.random() < 0.4
            self._repo.insert_entry(
                entry_id=entry_id,
                created_at_ms=created,
                # The server saw it later than the device recorded it. A queue
                # drained after the flight lands is what offline capture exists
                # for, and neither instant is ever corrected against the other.
                received_at_ms=created + self._rng.randrange(4 * MS_PER_HOUR),
                captured_tz=self._zone,
                tz_offset_min=self._offset_min,
                modality="voice" if voice else "text",
                raw_text=text,
                transcript_path=(
                    f"synthetic/transcripts/{entry_id}.txt" if voice else None
                ),
                audio_path=f"synthetic/audio/{entry_id}.wav" if voice else None,
                asr_provider="local-asr" if voice else None,
                asr_confidence=(
                    round(self._rng.uniform(0.82, 0.99), 3) if voice else None
                ),
                default_policy=self._policy,
                status="captured",
                title=title,
                source_device=self._rng.choice(_DEVICES),
                capture_profile=self._profile,
                offered_capability_json=self._offered_capability(),
                is_synthetic=True,
            )
            self._event(
                ts_ms=created,
                lane="capture",
                kind="note",
                label=f"captured under {self._policy}",
                entry_id=entry_id,
            )
            # The last two stay captured. A night that drains everything it was
            # offered hides the backlog the morning view exists to show.
            if index < count - 2:
                self._repo.transition_entry(entry_id, to_status="queued")
            ids.append(entry_id)

        self._repo.transition_entry(ids[0], to_status="running")
        return ids

    def _offered_capability(self) -> str:
        """What the capture surface offered, in the shape the API records.

        Kept because a cloud-assisted choice made while local-only was disabled
        is not the same choice as one made freely, and without this column the
        two are indistinguishable afterwards.
        """
        return json.dumps(
            {
                "profile": self._profile,
                "degraded": False,
                "degradation_reason": None,
                "policies": [
                    {
                        "policy": str(Policy.LOCAL_ONLY),
                        "available": True,
                        "reason": None,
                    },
                    {
                        "policy": str(Policy.CLOUD_ASSISTED),
                        "available": True,
                        "reason": None,
                    },
                ],
            }
        )

    # -- the run -----------------------------------------------------------

    def _open_run(self, entry_id: str) -> str:
        return self._repo.insert_run(
            run_id=self._mint(self._night.start_ms),
            entry_id=entry_id,
            night_of=self._night_of,
            started_at_ms=self._night.start_ms,
            effective_policy=self._policy,
            # The subject was captured under the policy the run executes, so
            # nothing upgraded it and no profile forced it.
            policy_source=str(PolicySource.ENTRY_DEFAULT),
            compute_profile=self._profile,
            brain_sha=self._sha(),
            code_sha=self._sha(),
            is_synthetic=True,
        )

    def _stages(self, windows: dict[str, _Span]) -> None:
        """Stage checkpoints, plus the boundary events the scrubber draws against.

        The final stage is left running, and that is a deliberate consequence of
        what the repository offers: there is no operation that closes a run, so
        a night whose every stage read `complete` would sit forever beside a run
        with no end and no outcome. A run still in flight is a state the system
        genuinely produces and the live view spends most of its time rendering,
        so the seed generates that one rather than an incoherent finished night.
        """
        final = STAGES[-1]
        for seq, stage in enumerate(STAGES, start=1):
            window = windows[stage]
            complete = stage != final
            self._repo.insert_run_stage(
                stage_id=self._mint(window.start_ms),
                run_id=self._run_id,
                stage=stage,
                seq=seq,
                status="complete" if complete else "running",
                started_at_ms=window.start_ms,
            )
            self._event(
                ts_ms=window.start_ms,
                lane="system",
                kind="stage_start",
                label=f"{stage} started",
            )
            if complete:
                self._event(
                    ts_ms=window.end_ms,
                    lane="system",
                    kind="stage_end",
                    label=f"{stage} complete",
                    duration_ms=window.duration_ms,
                )

    # -- the invocation tree ----------------------------------------------

    def _spawn(
        self, *, stage: str, role: str, span: _Span, parent: str | None, depth: int
    ) -> None:
        """Open one invocation, record its work, and recurse to the fanout depth.

        Left open on the way out. Outcomes are decided once the night's failures
        have been placed, because whether an invocation succeeded depends on
        whether one landed underneath it.
        """
        invocation_id = self._repo.insert_agent_invocation(
            invocation_id=self._mint(span.start_ms),
            agent_id=self._agent_for(role),
            run_id=self._run_id,
            parent_invocation_id=parent,
            depth=depth,
            stage=stage,
            input_summary=f"{SYNTHETIC} {stage}: {self._rng.choice(STAGE_WORK[stage])}",
            started_at_ms=span.start_ms,
            is_synthetic=True,
        )
        self._invocations.append(_Invocation(invocation_id, parent, stage, role, span))
        self._work(
            invocation_id=invocation_id, stage=stage, role=role, span=span, depth=depth
        )

        if depth >= len(_FANOUT):
            return
        low, high = _FANOUT[depth]
        _, helpers = _STAGE_ROLES[stage]
        for _ in range(self._rng.randint(low, high)):
            self._spawn(
                stage=stage,
                role=self._rng.choice(helpers),
                span=span.within(self._rng, self._rng.uniform(*_CHILD_SHARE)),
                parent=invocation_id,
                depth=depth + 1,
            )

    def _agent_for(self, role: str) -> str:
        """The agent row backing a role, created once per night.

        Read before insert because `agents` carries `UNIQUE(name, version)` and
        no `is_synthetic` column: the roster is a catalog rather than night
        data, so a second seeded night in the same database reuses it instead of
        colliding with it. The name carries the label the table cannot.
        """
        if role in self._agents:
            return self._agents[role]
        name = f"synthetic-{role}"
        existing = self._repo.connection.execute(
            "SELECT id FROM agents WHERE name = ? AND version = 1", (name,)
        ).fetchone()
        if existing is None:
            agent_id = self._repo.insert_agent(
                agent_id=self._mint(self._night.start_ms),
                name=name,
                role=role,
                version=1,
                prompt_path=f"synthetic/prompts/{role}.v1.md",
                prompt_sha=self._sha(),
                default_model_local=_MODELS[LOCAL][0],
                default_model_cloud=_MODELS[HOSTED][0],
            )
        else:
            agent_id = existing["id"]
        self._agents[role] = agent_id
        return agent_id

    def _work(
        self, *, invocation_id: str, stage: str, role: str, span: _Span, depth: int
    ) -> None:
        """The telemetry one invocation leaves behind.

        Four events at minimum — opened, at least one model call, at least one
        piece of stage work, closed — which is what makes the night's event
        floor arithmetic rather than luck.
        """
        calls = self._rng.randint(1, 3)
        activities = self._rng.randint(1, 4)
        instants = span.instants(self._rng, calls + activities)

        self._event(
            ts_ms=span.start_ms,
            lane=role,
            kind="note",
            label=f"{role} opened",
            invocation_id=invocation_id,
        )
        for ts in instants[:calls]:
            self._model_call(
                invocation_id=invocation_id,
                stage=stage,
                role=role,
                span=span,
                depth=depth,
                ts_ms=ts,
            )
        for ts in instants[calls:]:
            self._activity(
                invocation_id=invocation_id, stage=stage, role=role, ts_ms=ts
            )
        self._event(
            ts_ms=span.end_ms,
            lane=role,
            kind="note",
            label=f"{role} closed",
            invocation_id=invocation_id,
            duration_ms=span.duration_ms,
        )

    def _activity(
        self, *, invocation_id: str, stage: str, role: str, ts_ms: int
    ) -> None:
        """One piece of stage work, recorded as whatever that stage does."""
        kind = _STAGE_ACTIVITY[stage]
        duration = self._rng.randrange(2_000, 90_000)
        payload = None

        if kind == "search":
            if self._policy == str(Policy.CLOUD_ASSISTED):
                self._tool_call(
                    invocation_id=invocation_id, ts_ms=ts_ms, latency_ms=duration
                )
            else:
                # A local-only night makes no external tool call at all. The
                # airlock is a property of the run, not only of its model calls:
                # a search carries the idea off the machine just as surely.
                kind = "note"
        elif kind == "file_write":
            payload = {"path": output_path(stage, f"{role}-{self._events}")}

        self._event(
            ts_ms=ts_ms,
            lane=role,
            kind=kind,
            label=self._rng.choice(STAGE_WORK[stage]),
            invocation_id=invocation_id,
            duration_ms=duration,
            payload=payload,
        )

    # -- calls -------------------------------------------------------------

    def _provider_for(self, stage: str, depth: int) -> str:
        """Which backend served a call.

        Under `local-only` there is exactly one answer, and it is the only one
        the database CHECK will accept. Under `cloud-assisted` the escalations
        are structural rather than sampled — research reaches for the hosted
        reasoner, build dispatches a batch job — so every generated night has
        cloud spend to chart. A night whose spend depended on a coin flip would
        sometimes produce an empty cost curve, which is the one thing the curve
        must never do by accident.
        """
        if self._policy == str(Policy.LOCAL_ONLY):
            return LOCAL
        if depth <= 1:
            if stage == "build":
                return BATCH
            if stage == "research":
                return HOSTED
        return LOCAL if self._rng.random() < 0.7 else HOSTED

    def _model_call(
        self,
        *,
        invocation_id: str,
        stage: str,
        role: str,
        span: _Span,
        depth: int,
        ts_ms: int,
    ) -> None:
        provider = self._provider_for(stage, depth)
        # The call-time guard as well as the constraint. Both hold in real work,
        # and a generator that satisfied only the database could produce a night
        # the orchestrator would have refused to run.
        assert_permitted(self._policy, provider)

        model = self._rng.choice(_MODELS[provider])
        prompt_tokens = self._rng.randrange(900, 6_500)
        completion_tokens = self._rng.randrange(120, 1_400)
        reasoning = self._rng.random() < 0.4
        reasoning_tokens = self._rng.randrange(0, 900) if reasoning else 0
        latency = self._rng.randrange(700, 24_000)
        prompt_rate, completion_rate = _RATES_USD_PER_MTOK[provider]

        self._model_calls.append(
            self._repo.insert_model_call(
                call_id=self._mint(ts_ms),
                provider=provider,
                compute_profile=self._profile,
                model=model,
                model_version=f"{model}-v1",
                policy=self._policy,
                effort=self._rng.choice(("low", "medium", "high")),
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                reasoning_tokens=reasoning_tokens,
                total_tokens=prompt_tokens + completion_tokens + reasoning_tokens,
                latency_ms=latency,
                time_to_first_token_ms=latency // self._rng.randint(3, 9),
                estimated_cost_usd=(
                    prompt_tokens * prompt_rate + completion_tokens * completion_rate
                )
                / 1_000_000,
                cache_hit=self._rng.random() < 0.15,
                # Egress passes redaction; a local call never leaves the machine
                # and has nothing to redact.
                redaction_applied=is_remote(provider),
                agent_invocation_id=invocation_id,
                run_id=self._run_id,
                ts_ms=ts_ms,
                is_synthetic=True,
            )
        )
        self._event(
            ts_ms=ts_ms,
            lane=role,
            kind="model_call",
            label=f"{model} on {provider}",
            invocation_id=invocation_id,
            duration_ms=latency,
            payload={"provider": provider, "tokens": prompt_tokens + completion_tokens},
        )
        if provider == BATCH:
            # Dispatched work brackets the call, because that is what the
            # executor records: the night has to render the gap between handing
            # a job out and getting it back.
            self._event(
                ts_ms=ts_ms,
                lane="system",
                kind="job_dispatch",
                label=f"dispatched {stage} to {provider}",
                invocation_id=invocation_id,
            )
            self._event(
                ts_ms=min(ts_ms + latency, span.end_ms),
                lane="system",
                kind="job_complete",
                label=f"{stage} job returned",
                invocation_id=invocation_id,
                duration_ms=latency,
            )

    def _tool_call(self, *, invocation_id: str, ts_ms: int, latency_ms: int) -> None:
        self._tool_calls.append(
            self._repo.insert_tool_call(
                call_id=self._mint(ts_ms),
                tool="web-search",
                endpoint=self._rng.choice(("search", "extract", "crawl", "research")),
                policy=self._policy,
                # Only the redacted form is ever stored, for a generated query
                # as much as a real one — the column has no raw counterpart.
                query_redacted=f"{SYNTHETIC} {self._rng.choice(TOPICS)}",
                credits=round(self._rng.uniform(1.0, 5.0), 2),
                result_count=self._rng.randint(0, 12),
                latency_ms=latency_ms,
                cached=self._rng.random() < 0.2,
                outcome="success" if self._rng.random() < 0.9 else "quota",
                agent_invocation_id=invocation_id,
                run_id=self._run_id,
                ts_ms=ts_ms,
                is_synthetic=True,
            )
        )

    # -- failure -----------------------------------------------------------

    def _failures(self) -> list[tuple[str, str]]:
        """Place typed failures on the tree, returning (invocation, failure) pairs.

        A fixed count rather than a per-invocation probability: a night with no
        failures does not resemble a real one, and the failure ledger is a view
        a judge may well open on a seeded deployment.
        """
        # Only leaves fail. A stage lead that failed outright would contradict
        # the stage row above it, which recorded that stage as complete.
        leaves = [i for i in self._invocations if i.parent_id is not None]
        targets = self._rng.sample(leaves, self._rng.randint(*_FAILURES_PER_NIGHT))
        # Shuffled and walked in order rather than sampled independently, so the
        # taxonomy is covered instead of approximated: drawing at random leaves
        # a seeded ledger showing three types out of eight often enough to
        # matter. Past the end it wraps, which is where recurrence comes from.
        templates = list(_FAILURE_TEMPLATES)
        self._rng.shuffle(templates)
        placed: list[tuple[str, str]] = []

        for index, target in enumerate(targets):
            exc_type, message = templates[index % len(templates)]
            exc = exc_type(message)
            failure_type = classify(exc)
            ts = target.span.instants(self._rng, 1)[0]
            failure_id = self._repo.insert_failure(
                failure_id=self._mint(ts),
                failure_type=str(failure_type),
                signature=signature(failure_type, exc, scope=target.stage),
                message=message,
                run_id=self._run_id,
                agent_invocation_id=target.invocation_id,
                context_json=json.dumps({"stage": target.stage, "role": target.role}),
                ts_ms=ts,
                is_synthetic=True,
            )
            self._event(
                ts_ms=ts,
                lane=target.role,
                kind="error",
                label=f"{failure_type} in {target.stage}",
                invocation_id=target.invocation_id,
                severity="error",
            )
            # Around half stay open. A ledger in which everything is already
            # resolved never renders the state it exists to surface.
            if self._rng.random() < 0.5:
                self._repo.resolve_failure(
                    failure_id,
                    resolution=self._rng.choice(RESOLUTIONS),
                    resolved_at_ms=ts + self._rng.randrange(60_000, 20 * 60_000),
                )
            placed.append((target.invocation_id, failure_id))
        return placed

    def _close_invocations(self, *, failed: set[str]) -> None:
        """Close every invocation, degrading the ancestors of a failed one.

        Degraded rather than failed, because that is what the pipeline does: a
        stage whose child failed still commits what it had. Marking an ancestor
        failed would claim the night lost work it did not lose.
        """
        by_id = {i.invocation_id: i for i in self._invocations}
        degraded: set[str] = set()
        for invocation_id in failed:
            parent = by_id[invocation_id].parent_id
            while parent is not None:
                degraded.add(parent)
                parent = by_id[parent].parent_id

        for invocation in reversed(self._invocations):
            if invocation.invocation_id in failed:
                outcome = "failed"
            elif invocation.invocation_id in degraded:
                outcome = "degraded"
            else:
                outcome = "success"
            self._repo.close_invocation(
                invocation.invocation_id,
                outcome=outcome,
                ended_at_ms=invocation.span.end_ms,
                retry_count=0 if outcome == "success" else 1,
            )

    # -- helpers -----------------------------------------------------------

    def _event(
        self,
        *,
        ts_ms: int,
        lane: str,
        kind: str,
        label: str,
        invocation_id: str | None = None,
        entry_id: str | None = None,
        severity: str = "info",
        duration_ms: int | None = None,
        payload: dict[str, object] | None = None,
    ) -> None:
        self._repo.insert_event(
            lane=lane,
            kind=kind,
            label=label,
            # Capture happens before there is a run to attach to. Migration 0002
            # added `entry_id` for exactly that, so those events stay readable
            # through `entry_history` instead of falling out of the feed.
            run_id=self._run_id or None,
            agent_invocation_id=invocation_id,
            entry_id=entry_id,
            ts_ms=ts_ms,
            severity=severity,
            duration_ms=duration_ms,
            payload_json=json.dumps(payload) if payload is not None else None,
            is_synthetic=True,
        )
        self._events += 1

    def _sha(self) -> str:
        """A commit-shaped identifier drawn from the seeded stream."""
        return f"{self._rng.getrandbits(160):040x}"
