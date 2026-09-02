"""The local reasoner: vLLM over its OpenAI-compatible endpoint.

The standard library talks to it. `config.py` already probes this server with
`urllib`, and a client library for one endpoint and four response fields would
add a dependency to do what `urllib` and `json` do — against a server chosen for
speaking an ordinary protocol.

Nothing here writes telemetry. `Reasoner` records the call, the failure and a
completion that did not stop cleanly; this file's whole job is to produce a
`RawCompletion` or to raise.

Serving configuration is `docs/MODELS.md` and
`scripts/spikes/spike-b-local-inference/FINDINGS.md`. The endpoint, the
served-model name and the sampling parameters are configuration, read through
`config.local_reasoner_settings()`.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request

from ..config import LocalReasonerSettings, local_reasoner_settings
from ..telemetry.failures import BadOutput
from ..telemetry.recorder import Recorder
from .base import Message, RawCompletion, Reasoner

COMPLETIONS_PATH = "/v1/chat/completions"


class ReasonerUnavailable(ConnectionError):
    """The local reasoner could not be reached, or refused the request.

    A `ConnectionError` deliberately: the failure taxonomy classifies by
    exception type as well as by message, and this is a network failure whatever
    the endpoint's own words for it were.
    """


class ReasonerTimeout(ReasonerUnavailable, TimeoutError):
    """The local reasoner did not answer within the configured timeout.

    Both bases carry meaning. `TimeoutError` is checked before `ConnectionError`
    when a failure is classified, so this lands as a model timeout rather than a
    network fault — the distinction between a server that is absent and one that
    is too slow is the whole reason the taxonomy separates them.
    """


class VllmReasoner(Reasoner):
    """Text completion from the local inference server."""

    provider_kind = "local-vllm"

    def __init__(
        self, recorder: Recorder, *, settings: LocalReasonerSettings | None = None
    ) -> None:
        resolved = settings if settings is not None else local_reasoner_settings()
        super().__init__(recorder, model=resolved.model)
        self._settings = resolved

    @property
    def endpoint(self) -> str:
        return f"{self._settings.base_url}{COMPLETIONS_PATH}"

    def _do_complete(
        self, messages: list[Message], *, effort: str | None
    ) -> RawCompletion:
        """One completion, from the server's own numbers.

        `effort` is recorded by the base class and deliberately does not change
        the request. The escalation policy in `docs/MODELS.md` is explicit that
        `local-only` never escalates, and this profile serves exactly one model —
        varying sampling by effort would invent a policy nobody decided.
        """
        return _read_completion(
            self.endpoint,
            self._post(
                {
                    "model": self._settings.model,
                    "messages": [
                        {"role": m.role, "content": m.content} for m in messages
                    ],
                    "max_tokens": self._settings.max_tokens,
                    "temperature": self._settings.temperature,
                    "stream": False,
                }
            ),
        )

    def _post(self, payload: dict) -> dict:
        request = urllib.request.Request(
            self.endpoint,
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        timeout = self._settings.timeout_s
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                raw = response.read()
        except urllib.error.HTTPError as exc:
            # The server's own words, carried through: a 500 whose body says
            # "CUDA out of memory" is classified as an OOM rather than as a
            # generic network fault, and only because the body reaches the
            # ledger.
            detail = _describe(exc)
            raise ReasonerUnavailable(
                f"local reasoner at {self.endpoint} returned {exc.code}: {detail}"
            ) from exc
        except TimeoutError as exc:
            raise ReasonerTimeout(
                f"local reasoner at {self.endpoint} did not answer within {timeout}s"
            ) from exc
        except urllib.error.URLError as exc:
            if isinstance(exc.reason, TimeoutError):
                raise ReasonerTimeout(
                    f"local reasoner at {self.endpoint} did not answer within "
                    f"{timeout}s"
                ) from exc
            raise ReasonerUnavailable(
                f"local reasoner at {self.endpoint} unreachable: {exc.reason}"
            ) from exc
        except OSError as exc:
            raise ReasonerUnavailable(
                f"local reasoner at {self.endpoint} unreachable: {exc}"
            ) from exc

        try:
            body = json.loads(raw)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise BadOutput(
                f"local reasoner at {self.endpoint} answered with something that "
                f"is not JSON: {exc}"
            ) from exc
        if not isinstance(body, dict):
            raise BadOutput(
                f"local reasoner at {self.endpoint} answered with "
                f"{type(body).__name__}, not an object"
            )
        return body


def _describe(exc: urllib.error.HTTPError) -> str:
    """The server's error body, or its reason if the body is unreadable."""
    try:
        detail = exc.read().decode(errors="replace").strip()
    except OSError:
        detail = ""
    return (detail or str(exc.reason))[:500]


def _read_completion(endpoint: str, body: dict) -> RawCompletion:
    """Read one chat completion, refusing anything that is not one."""
    choices = body.get("choices")
    if not isinstance(choices, list) or not choices:
        raise BadOutput(f"local reasoner at {endpoint} answered with no choices")
    choice = choices[0]
    if not isinstance(choice, dict):
        raise BadOutput(f"local reasoner at {endpoint} answered with an unreadable choice")
    message = choice.get("message")
    if not isinstance(message, dict):
        raise BadOutput(f"local reasoner at {endpoint} answered with no message")

    text = message.get("content") or ""
    if not isinstance(text, str):
        raise BadOutput(
            f"local reasoner at {endpoint} answered with content that is "
            f"{type(text).__name__}, not text"
        )

    usage = body.get("usage")
    usage = usage if isinstance(usage, dict) else {}
    details = usage.get("completion_tokens_details")
    details = details if isinstance(details, dict) else {}

    prompt_tokens = _count(usage.get("prompt_tokens"))
    completion_tokens = _count(usage.get("completion_tokens"))
    reasoning_tokens = _count(details.get("reasoning_tokens"))

    # The recorder sums prompt, completion and reasoning into one total, so the
    # three must be disjoint. OpenAI-compatible usage nests reasoning *inside*
    # the completion count, and passing both through unchanged would inflate
    # every local call by the length of its own thinking.
    return RawCompletion(
        text=text,
        prompt_tokens=prompt_tokens,
        completion_tokens=max(0, completion_tokens - reasoning_tokens),
        reasoning_tokens=reasoning_tokens,
        cache_hit=bool(usage.get("prompt_cache_hit")),
        finish_reason=str(choice.get("finish_reason") or ""),
    )


def _count(value: object) -> int:
    """A token count, or zero. A malformed count is not worth failing a call for."""
    return value if isinstance(value, int) and not isinstance(value, bool) and value > 0 else 0
