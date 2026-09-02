"""Provider registry.

Binds the four interfaces to implementations by resolved compute profile. This
is the single place that knows which backend is in play, which is what keeps
provider specifics out of the agents, the night state machine and the API.

Real backends register here as their spikes land. A local profile binds the vLLM
reasoner; the remaining three, and every provider on `cloud`, are still null
implementations, so the orchestrator runs end to end without them.

A missing backend is a refusal, not a substitution. Binding an echo where a model
should be produces a system that answers, records a model call, and reasons about
nothing — which is what it did until this reasoner landed.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..config import local_reasoner_settings
from ..telemetry.recorder import Recorder
from .base import Embedder, Executor, Reasoner, Transcriber
from .null import EchoReasoner, HashEmbedder, InProcessExecutor, NullTranscriber
from .vllm import VllmReasoner


class LocalReasonerNotConfigured(RuntimeError):
    """A local profile was bound with no served-model name configured.

    Raised rather than quietly binding an echo. A registry that substitutes a
    placeholder when the real backend is missing is how this system spent a week
    appearing to reason while returning its own input.
    """


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
            reasoner=self._local_reasoner(),
            transcriber=NullTranscriber(recorder, model="local-placeholder"),
            embedder=HashEmbedder(recorder, model="local-placeholder"),
            executor=InProcessExecutor(recorder, model="local-placeholder"),
        )

    def _local_reasoner(self) -> Reasoner:
        """The real local backend, or a clear refusal.

        A profile only resolves to `spark` or `workstation` when the probe has
        confirmed an endpoint serving the expected model *by name*, so on those
        profiles the endpoint is real and binding to it is correct.
        """
        settings = local_reasoner_settings()
        if not settings.model:
            raise LocalReasonerNotConfigured(
                "a local profile needs the served-model name the inference server "
                "reports for itself; set `reasoner_model` in config/models.toml, "
                "or SECOND_SHIFT_LOCAL_MODEL. Refusing to bind a placeholder that "
                "would answer without a model."
            )
        return VllmReasoner(self._recorder, settings=settings)
