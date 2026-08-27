"""Null providers.

Deterministic, dependency-free implementations used by tests and by a profile
with no backend configured. They exist so the foundation is exercisable before
any spike lands: a failed vLLM or NeMo build on days 4-6 does not stop the
orchestrator from running end to end.

Every one overrides only its `_do_*` method and contains no telemetry code —
which is the property the base classes exist to guarantee.
"""

from __future__ import annotations

from .base import (
    Embedder,
    Executor,
    JobHandle,
    JobResult,
    JobSpec,
    Message,
    RawCompletion,
    Reasoner,
    Transcriber,
    Transcript,
)
from ..telemetry.recorder import TelemetryDescriptor


class EchoReasoner(Reasoner):
    """Returns the last message, with token counts derived from length."""

    provider_kind = "local-vllm"

    def _do_complete(
        self, messages: list[Message], *, effort: str | None
    ) -> RawCompletion:
        prompt = " ".join(m.content for m in messages)
        text = messages[-1].content if messages else ""
        return RawCompletion(
            text=text,
            prompt_tokens=max(1, len(prompt) // 4),
            completion_tokens=max(1, len(text) // 4),
        )


class NullTranscriber(Transcriber):
    provider_kind = "local-vllm"

    def _do_transcribe(self, audio: bytes) -> Transcript:
        return Transcript(text="", confidence=0.0)


class HashEmbedder(Embedder):
    """Deterministic pseudo-embeddings. Stable across runs, no model required."""

    provider_kind = "local-vllm"
    dimensions = 16

    def _do_embed(self, texts: list[str]) -> list[list[float]]:
        vectors = []
        for text in texts:
            seed = hash(text)
            vectors.append(
                [((seed >> (i * 3)) & 0xFF) / 255.0 for i in range(self.dimensions)]
            )
        return vectors


class InProcessExecutor(Executor):
    """Runs jobs immediately and locally. Stands in for Serverless Jobs."""

    provider_kind = "nebius-job"

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._jobs: dict[str, JobSpec] = {}
        self._descriptors: dict[str, TelemetryDescriptor] = {}
        self._counter = 0

    def _do_dispatch(
        self, job: JobSpec, *, telemetry: TelemetryDescriptor
    ) -> JobHandle:
        self._counter += 1
        job_id = f"job-{self._counter:04d}"
        self._jobs[job_id] = job
        self._descriptors[job_id] = telemetry
        return JobHandle(job_id=job_id)

    def _do_await_result(self, handle: JobHandle) -> JobResult:
        job = self._jobs[handle.job_id]
        return JobResult(
            job_id=handle.job_id,
            status="success",
            artifacts=[f"{job.kind}.md"],
            payload={"kind": job.kind},
        )

    def descriptor_seen(self, job_id: str) -> TelemetryDescriptor:
        """Test seam: what descriptor did the remote side receive?"""
        return self._descriptors[job_id]
