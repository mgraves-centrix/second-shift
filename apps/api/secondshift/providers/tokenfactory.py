"""The cloud reasoner: Nebius Token Factory, over its OpenAI-compatible API.

The system's first remote reasoner, for the turns ADR 0004 assigns to the cloud.
It changes nothing about what may leave the machine: `Reasoner.complete`
refuses it under `local-only` before a request is built, and the `model_calls`
CHECK would refuse to record one if anything got past that. What is new is a
credential.

The key is read from the environment when a call is made, sent only as the
bearer token, and never placed in a message, a failure, or a recorded field. A
server that echoes it back in an error has it removed before the error is
raised, because that error becomes a failure row and failure rows are read.

What this does not do is decide what text may be sent. That is the caller's,
and for a `cloud-assisted` idea it is a redaction step and a policy-filtered
context that do not exist yet; `night/__main__.py` refuses the cloud profile
until they do.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

from ..config import ENV_NEBIUS_KEY, CloudReasonerSettings, cloud_reasoner_settings
from ..telemetry.failures import BadOutput
from ..telemetry.recorder import Recorder
from .base import Message, RawCompletion, Reasoner
from .vllm import _describe, _read_completion

SOURCE = "Token Factory"


class CloudReasonerNotConfigured(RuntimeError):
    """No credential, or no model, for the cloud reasoner.

    Raised at the call rather than at binding, so a deployment with no key — the
    judge instance — still starts, and still cannot pretend to reason.
    """


class CloudReasonerUnavailable(ConnectionError):
    """Token Factory could not be reached, or refused the request."""


class TokenFactoryReasoner(Reasoner):
    """Text completion from Token Factory."""

    provider_kind = "token-factory"

    def __init__(
        self, recorder: Recorder, *, settings: CloudReasonerSettings | None = None
    ) -> None:
        resolved = settings if settings is not None else cloud_reasoner_settings()
        super().__init__(recorder, model=resolved.model)
        self._settings = resolved

    @property
    def endpoint(self) -> str:
        return f"{self._settings.base_url}/chat/completions"

    def _do_complete(
        self, messages: list[Message], *, effort: str | None
    ) -> RawCompletion:
        key = os.environ.get(ENV_NEBIUS_KEY, "")
        if not key or not self._settings.model:
            missing = ENV_NEBIUS_KEY if not key else "[cloud] reasoner_model"
            raise CloudReasonerNotConfigured(
                f"the cloud reasoner has no {missing}. Refusing rather than "
                "answering with something that did not reason."
            )
        payload = {
            "model": self._settings.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "max_tokens": self._settings.max_tokens,
            "temperature": self._settings.temperature,
            "stream": False,
        }
        request = urllib.request.Request(
            self.endpoint,
            data=json.dumps(payload).encode(),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {key}",
            },
            method="POST",
        )
        timeout = self._settings.timeout_s
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                raw = response.read()
        # `from None` throughout: a server that echoes the key in its error body
        # would otherwise carry it in the chained exception, which a traceback
        # prints and a failure row may keep.
        except urllib.error.HTTPError as exc:
            detail = _describe(exc).replace(key, "<redacted>")
            raise CloudReasonerUnavailable(
                f"{SOURCE} at {self.endpoint} returned {exc.code}: {detail}"
            ) from None
        except TimeoutError:
            raise CloudReasonerUnavailable(
                f"{SOURCE} at {self.endpoint} did not answer within {timeout}s"
            ) from None
        except (urllib.error.URLError, OSError) as exc:
            reason = getattr(exc, "reason", exc)
            raise CloudReasonerUnavailable(
                f"{SOURCE} at {self.endpoint} unreachable: {reason}"
            ) from None

        try:
            body = json.loads(raw)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise BadOutput(
                f"{SOURCE} at {self.endpoint} answered with something that is not "
                f"JSON: {exc}"
            ) from None
        if not isinstance(body, dict):
            raise BadOutput(
                f"{SOURCE} at {self.endpoint} answered with "
                f"{type(body).__name__}, not an object"
            )
        return _read_completion(self.endpoint, body, source=SOURCE)
