"""The local embedder: vLLM over its OpenAI-compatible embeddings endpoint.

The same server type the reasoner uses, on its own port. `urllib` and `json`
talk to it, for the reason `vllm.py` gives: a client library for one endpoint
would add a dependency to do what the standard library does.

Nothing here writes telemetry. `Embedder` records the event and the failure;
this file's whole job is to return vectors or to raise.

Retrieval runs locally on every profile — ADR 0002 and principle 2 both — so
`provider_kind` is a local kind and there is deliberately no remote embedder
anywhere in this package to select instead.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request

from ..config import LocalEmbedderSettings, local_embedder_settings
from ..telemetry.failures import BadOutput
from ..telemetry.recorder import Recorder
from .base import Embedder

EMBEDDINGS_PATH = "/v1/embeddings"


class EmbedderUnavailable(ConnectionError):
    """The local embedder could not be reached, or refused the request.

    A `ConnectionError` for the same reason `ReasonerUnavailable` is one: the
    failure taxonomy classifies by exception type, and this is a network
    failure whatever the endpoint called it.
    """


class EmbedderTimeout(EmbedderUnavailable, TimeoutError):
    """The local embedder did not answer within the configured timeout."""


class VllmEmbedder(Embedder):
    """Vectors from the local embedding server."""

    provider_kind = "local-vllm"

    def __init__(
        self, recorder: Recorder, *, settings: LocalEmbedderSettings | None = None
    ) -> None:
        resolved = settings if settings is not None else local_embedder_settings()
        super().__init__(recorder, model=resolved.model)
        self._settings = resolved

    @property
    def endpoint(self) -> str:
        return f"{self._settings.base_url}{EMBEDDINGS_PATH}"

    @property
    def dimensions(self) -> int:
        return self._settings.dimensions

    def _do_embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        body = self._post({"model": self._settings.model, "input": texts})
        return _read_embeddings(self.endpoint, body, len(texts), self.dimensions)

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
            raise EmbedderUnavailable(
                f"local embedder at {self.endpoint} returned {exc.code}: "
                f"{_describe(exc)}"
            ) from exc
        except TimeoutError as exc:
            raise EmbedderTimeout(
                f"local embedder at {self.endpoint} did not answer within {timeout}s"
            ) from exc
        except urllib.error.URLError as exc:
            if isinstance(exc.reason, TimeoutError):
                raise EmbedderTimeout(
                    f"local embedder at {self.endpoint} did not answer within "
                    f"{timeout}s"
                ) from exc
            raise EmbedderUnavailable(
                f"local embedder at {self.endpoint} unreachable: {exc.reason}"
            ) from exc
        except OSError as exc:
            raise EmbedderUnavailable(
                f"local embedder at {self.endpoint} unreachable: {exc}"
            ) from exc

        try:
            parsed = json.loads(raw)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise BadOutput(
                f"local embedder at {self.endpoint} answered with something that "
                f"is not JSON: {exc}"
            ) from exc
        if not isinstance(parsed, dict):
            raise BadOutput(
                f"local embedder at {self.endpoint} answered with "
                f"{type(parsed).__name__}, not an object"
            )
        return parsed


def _describe(exc: urllib.error.HTTPError) -> str:
    """The server's error body, or its reason if the body is unreadable."""
    try:
        detail = exc.read().decode(errors="replace").strip()
    except OSError:
        detail = ""
    return (detail or str(exc.reason))[:500]


def _read_embeddings(
    endpoint: str, body: dict, expected_count: int, expected_dimensions: int
) -> list[list[float]]:
    """Read one embeddings response, refusing anything that is not one.

    Ordered by each item's own `index` rather than by arrival. The OpenAI
    embeddings schema carries an index precisely because the array is not
    promised to be in request order, and a caller that zips vectors back onto
    its inputs positionally would attach the wrong vector to the wrong document
    without anything looking broken.
    """
    data = body.get("data")
    if not isinstance(data, list):
        raise BadOutput(f"local embedder at {endpoint} answered with no data array")
    if len(data) != expected_count:
        raise BadOutput(
            f"local embedder at {endpoint} returned {len(data)} vectors for "
            f"{expected_count} inputs"
        )

    ordered: list[tuple[int, list[float]]] = []
    for position, item in enumerate(data):
        if not isinstance(item, dict):
            raise BadOutput(
                f"local embedder at {endpoint} answered with an unreadable "
                f"item at position {position}"
            )
        vector = item.get("embedding")
        if not isinstance(vector, list) or not vector:
            raise BadOutput(
                f"local embedder at {endpoint} answered with no embedding at "
                f"position {position}"
            )
        if len(vector) != expected_dimensions:
            raise BadOutput(
                f"local embedder at {endpoint} returned a {len(vector)}-dim "
                f"vector where {expected_dimensions} was configured — the "
                f"served model is not the one this index was built for"
            )
        floats = [float(v) for v in vector if isinstance(v, (int, float))]
        if len(floats) != len(vector):
            raise BadOutput(
                f"local embedder at {endpoint} returned a vector containing "
                f"something that is not a number, at position {position}"
            )
        index = item.get("index")
        ordered.append((index if isinstance(index, int) else position, floats))

    ordered.sort(key=lambda pair: pair[0])
    return [vector for _, vector in ordered]
