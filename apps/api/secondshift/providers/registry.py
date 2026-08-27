"""Provider registry.

Binds the four interfaces to implementations by resolved compute profile. This
is the single place that knows which backend is in play, which is what keeps
provider specifics out of the agents, the night state machine and the API.

Real backends register here as their spikes land. Until then every profile
resolves to the null implementations, so the orchestrator runs end to end
without a model.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..telemetry.recorder import Recorder
from .base import Embedder, Executor, Reasoner, Transcriber
from .null import EchoReasoner, HashEmbedder, InProcessExecutor, NullTranscriber


@dataclass(frozen=True, slots=True)
class Providers:
    """The bound set for one profile."""

    reasoner: Reasoner
    transcriber: Transcriber
    embedder: Embedder
    executor: Executor


class Registry:
    def __init__(self, recorder: Recorder) -> None:
        self._recorder = recorder

    def bind(self, profile: str) -> Providers:
        """Return the implementations for a resolved profile.

        Local backends are constructed only where the profile has local
        capability. On `cloud` no local backend is constructed at all, which is
        what makes `local-only` genuinely unavailable there rather than merely
        discouraged.
        """
        recorder = self._recorder
        if profile == "cloud":
            return Providers(
                reasoner=EchoReasoner(recorder, model="cloud-placeholder"),
                transcriber=NullTranscriber(recorder, model="cloud-placeholder"),
                embedder=HashEmbedder(recorder, model="cloud-placeholder"),
                executor=InProcessExecutor(recorder, model="cloud-placeholder"),
            )
        return Providers(
            reasoner=EchoReasoner(recorder, model="local-placeholder"),
            transcriber=NullTranscriber(recorder, model="local-placeholder"),
            embedder=HashEmbedder(recorder, model="local-placeholder"),
            executor=InProcessExecutor(recorder, model="local-placeholder"),
        )
