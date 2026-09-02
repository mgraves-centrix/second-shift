"""Provider registry.

Binds the four interfaces to implementations by resolved compute profile. This
is the single place that knows which backend is in play, which is what keeps
provider specifics out of the agents, the night state machine and the API.

Real backends register here as their spikes land. A local profile binds the vLLM
reasoner, and every profile binds the vLLM embedder — retrieval is local
everywhere, which is principle 2 rather than a deployment preference. The
transcriber and executor are still null implementations, so the orchestrator
runs end to end without them.

A missing backend is a refusal, not a substitution. Binding an echo where a model
should be produces a system that answers, records a model call, and reasons about
nothing — which is what it did until this reasoner landed.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..config import local_embedder_settings, local_reasoner_settings
from ..telemetry.recorder import Recorder
from .base import Embedder, Executor, Reasoner, Transcriber
from .null import EchoReasoner, InProcessExecutor, NullTranscriber
from .vllm import VllmReasoner
from .vllm_embed import VllmEmbedder


class LocalReasonerNotConfigured(RuntimeError):
    """A local profile was bound with no served-model name configured.

    Raised rather than quietly binding an echo. A registry that substitutes a
    placeholder when the real backend is missing is how this system spent a week
    appearing to reason while returning its own input.
    """


class LocalEmbedderNotConfigured(RuntimeError):
    """A profile was bound with no embedding server configured.

    The same refusal as the reasoner's, and for a sharper reason. `HashEmbedder`
    does not fail when it stands in for a real embedder — it returns plausible
    vectors of the right shape, and retrieval built on them ranks documents by
    the hash of their text. Nothing downstream can tell that from working
    retrieval, so the substitution has to be refused here or not at all.
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

        The local *reasoner* is constructed only where the profile has local
        capability: on `cloud` it is not, which is what makes `local-only`
        genuinely unavailable there rather than merely discouraged.

        The embedder is the exception, and deliberately. Retrieval is local on
        every profile including `cloud`, so the embedder is bound the same way
        everywhere — see `_local_embedder`.
        """
        recorder = self._recorder
        if profile == "cloud":
            return Providers(
                reasoner=EchoReasoner(recorder, model="cloud-placeholder"),
                transcriber=NullTranscriber(recorder, model="cloud-placeholder"),
                embedder=self._local_embedder(),
                executor=InProcessExecutor(recorder, model="cloud-placeholder"),
            )
        return Providers(
            reasoner=self._local_reasoner(),
            transcriber=NullTranscriber(recorder, model="local-placeholder"),
            embedder=self._local_embedder(),
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

    def _local_embedder(self) -> Embedder:
        """The local embedding backend, on every profile, or a clear refusal.

        Deliberately not branched by profile, unlike the reasoner. Principle 2
        requires retrieval to run locally on *every* compute profile and names a
        hosted embedding endpoint as a violation, so `cloud` gets the same local
        embedder as `spark` — there is no remote embedder in this package to
        select, and no configuration that could reach one.

        `docs/ARCHITECTURE.md`'s profile table disagrees: its `cloud` column
        reads "Token Factory embeddings". The constitution outranks it and
        that table is wrong; see this change's proposal.
        """
        settings = local_embedder_settings()
        if not settings.model:
            raise LocalEmbedderNotConfigured(
                "retrieval needs a local embedding server on every profile; set "
                "`embedder_model` in config/models.toml, or "
                "SECOND_SHIFT_EMBEDDER_MODEL. Refusing to bind the hash "
                "placeholder, whose vectors are the right shape and rank "
                "documents by nothing."
            )
        return VllmEmbedder(self._recorder, settings=settings)
