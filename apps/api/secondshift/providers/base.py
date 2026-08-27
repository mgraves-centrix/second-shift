"""Provider interfaces.

Four narrow interfaces, one registry. Every public method is concrete and owns
its telemetry; implementations override an internal `_do_*` method only. An
implementation that forgets to record telemetry is not possible, because it
never writes any — the base class does.

No concrete backend lives here. Real backends arrive with their spikes, and
keeping this module free of provider SDKs is what lets a failed spike leave the
foundation untouched.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from ..airlock.policy import assert_permitted
from ..telemetry.recorder import Recorder, TelemetryDescriptor


# -- value types -----------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Transcript:
    text: str
    confidence: float | None = None


@dataclass(frozen=True, slots=True)
class Message:
    role: str
    content: str


@dataclass(frozen=True, slots=True)
class RawCompletion:
    """What an implementation returns. Token counts come from the backend."""

    text: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    reasoning_tokens: int = 0
    cache_hit: bool = False


@dataclass(frozen=True, slots=True)
class Completion:
    """What a caller receives, with the recorded call's id attached."""

    text: str
    model_call_id: str
    prompt_tokens: int
    completion_tokens: int


@dataclass(frozen=True, slots=True)
class JobSpec:
    kind: str
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class JobHandle:
    job_id: str


@dataclass(frozen=True, slots=True)
class JobResult:
    """The work product only.

    Telemetry never travels here: out-of-process work reports it over its own
    channel, which keeps this interface independent of any serialization
    format. See `docs/decisions/0004` and the design doc.
    """

    job_id: str
    status: str
    artifacts: list[str] = field(default_factory=list)
    payload: dict[str, Any] = field(default_factory=dict)


# -- interfaces ------------------------------------------------------------


class Provider(ABC):
    """Common base: every provider knows its kind and its recorder."""

    #: One of the `model_calls.provider` values. Determines whether the airlock
    #: treats this provider as remote.
    provider_kind: str = "other"

    def __init__(self, recorder: Recorder, *, model: str = "") -> None:
        self._recorder = recorder
        self._model = model

    @property
    def model(self) -> str:
        return self._model


class Reasoner(Provider):
    """Text completion."""

    def complete(
        self,
        messages: list[Message],
        *,
        policy: str,
        effort: str | None = None,
        redaction_applied: bool = False,
    ) -> Completion:
        """Run a completion, recording it.

        `policy` is explicit rather than read from context. The airlock is the
        one place where an implicit value would be dangerous, so it is passed
        and asserted at every call.
        """
        assert_permitted(policy, self.provider_kind)

        started = time.perf_counter()
        raw = self._do_complete(messages, effort=effort)
        latency_ms = int((time.perf_counter() - started) * 1000)

        call_id = self._recorder.record_model_call(
            provider=self.provider_kind,
            model=self._model,
            policy=policy,
            prompt_tokens=raw.prompt_tokens,
            completion_tokens=raw.completion_tokens,
            reasoning_tokens=raw.reasoning_tokens,
            latency_ms=latency_ms,
            effort=effort,
            cache_hit=raw.cache_hit,
            redaction_applied=redaction_applied,
        )
        return Completion(
            text=raw.text,
            model_call_id=call_id,
            prompt_tokens=raw.prompt_tokens,
            completion_tokens=raw.completion_tokens,
        )

    @abstractmethod
    def _do_complete(
        self, messages: list[Message], *, effort: str | None
    ) -> RawCompletion:
        """Produce a completion. Implementations write no telemetry."""


class Transcriber(Provider):
    """Speech to text."""

    def transcribe(self, audio: bytes, *, policy: str) -> Transcript:
        assert_permitted(policy, self.provider_kind)
        started = time.perf_counter()
        transcript = self._do_transcribe(audio)
        self._recorder.record_event(
            lane="capture",
            kind="note",
            label=f"transcribed {len(audio)} bytes",
            duration_ms=int((time.perf_counter() - started) * 1000),
        )
        return transcript

    @abstractmethod
    def _do_transcribe(self, audio: bytes) -> Transcript: ...


class Embedder(Provider):
    """Text to vectors.

    Retrieval runs locally on every profile, so an embedder is never remote.
    """

    def embed(self, texts: list[str], *, policy: str) -> list[list[float]]:
        assert_permitted(policy, self.provider_kind)
        started = time.perf_counter()
        vectors = self._do_embed(texts)
        self._recorder.record_event(
            lane="retrieval",
            kind="note",
            label=f"embedded {len(texts)} texts",
            duration_ms=int((time.perf_counter() - started) * 1000),
        )
        return vectors

    @abstractmethod
    def _do_embed(self, texts: list[str]) -> list[list[float]]: ...


class Executor(Provider):
    """Out-of-process work."""

    provider_kind = "nebius-job"

    def dispatch(self, job: JobSpec, *, telemetry: TelemetryDescriptor) -> JobHandle:
        """Send work elsewhere.

        The descriptor tells the remote side where to report telemetry and which
        invocation it attaches under, so remote work appears in the tree at full
        depth instead of as an opaque span.
        """
        handle = self._do_dispatch(job, telemetry=telemetry)
        self._recorder.record_event(
            lane="executor",
            kind="job_dispatch",
            label=f"dispatched {job.kind} as {handle.job_id}",
        )
        return handle

    def await_result(self, handle: JobHandle) -> JobResult:
        started = time.perf_counter()
        result = self._do_await_result(handle)
        self._recorder.record_event(
            lane="executor",
            kind="job_complete",
            label=f"{handle.job_id} {result.status}",
            duration_ms=int((time.perf_counter() - started) * 1000),
            severity="info" if result.status == "success" else "warn",
        )
        return result

    @abstractmethod
    def _do_dispatch(
        self, job: JobSpec, *, telemetry: TelemetryDescriptor
    ) -> JobHandle: ...

    @abstractmethod
    def _do_await_result(self, handle: JobHandle) -> JobResult: ...
