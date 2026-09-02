"""Tavily search and extract, over the documented HTTP API.

`urllib`/`json` against the endpoints directly, mirroring `VllmReasoner`: no
SDK, no new dependency, and no wheel to build on aarch64.

**Nothing here fabricates a result.** With no credential the constructor raises;
it never returns a plausible search. The stand-in used by tests lives in the test
module rather than in this package, so there is no importable object that could
put invented results into `tool_calls` — the same property `EchoReasoner` has by
returning its own input, and the reason the credit accounting can be trusted.

This provider has **never made a real call**. No credential was available where
it was written, and obtaining one was out of scope. It is unproven against the
live API in exactly the way `VllmReasoner` was unproven before the Spark served
it, and that is recorded rather than implied away.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field

from ..telemetry.failures import ToolQuotaExceeded

ENV_TAVILY_KEY = "TAVILY_API_KEY"

_BASE = "https://api.tavily.com"

#: The endpoints the night needs. `crawl` is in the schema's CHECK and is
#: deliberately unused: crawling the web at large is not what a brief needs, and
#: it is the endpoint most likely to fetch something nobody asked for.
SEARCH = "search"
EXTRACT = "extract"

#: Statuses that mean "you are out of credits", not "something went wrong".
#: Raised as a typed failure so `classify()` maps it to `tool_quota` and the
#: night degrades rather than ending — the same treatment a model timeout gets.
_QUOTA_STATUSES = frozenset({402, 429})


class TavilyNotConfigured(RuntimeError):
    """No search credential is configured.

    Raised at construction rather than at call time, so a night that cannot
    search finds out before it has built a query rather than after.
    """


@dataclass(frozen=True, slots=True)
class SearchResult:
    """One result, reduced to what a brief can use."""

    title: str
    url: str
    snippet: str
    score: float = 0.0


@dataclass(frozen=True, slots=True)
class SearchResponse:
    results: list[SearchResult] = field(default_factory=list)
    latency_ms: int = 0
    #: Tavily bills per call rather than per result; recorded per row so a run's
    #: spend is a sum over `tool_calls` and never a stored total.
    credits: float = 1.0
    cached: bool = False


class TavilyProvider:
    """Search and extract. Takes an already-redacted query and trusts it.

    Deliberately: this class must not be the place redaction happens, or every
    future provider would have to remember to do it. `airlock.redact` owns that,
    the research stage calls it, and this receives a query that is already safe.
    A provider that redacted would also be a provider that could stop.
    """

    tool = "tavily"

    def __init__(self, *, api_key: str | None = None, timeout_s: float = 20.0) -> None:
        key = api_key or os.environ.get(ENV_TAVILY_KEY)
        if not key:
            raise TavilyNotConfigured(
                f"{ENV_TAVILY_KEY} is not set. Research needs a search credential; "
                "there is deliberately no offline mode that returns invented "
                "results, because a fabricated row is indistinguishable from a "
                "real one in `tool_calls` and the credit curve is a measurement."
            )
        self._key = key
        self._timeout_s = timeout_s

    def search(self, query: str, *, max_results: int = 5) -> SearchResponse:
        """One search. `query` is expected to be redacted already."""
        payload = {
            "query": query,
            "max_results": max_results,
            "search_depth": "basic",
        }
        raw, latency_ms = self._post(f"{_BASE}/search", payload)
        results = [
            SearchResult(
                title=str(r.get("title", "")),
                url=str(r.get("url", "")),
                snippet=str(r.get("content", "")),
                score=float(r.get("score", 0.0) or 0.0),
            )
            for r in raw.get("results", [])
            if isinstance(r, dict)
        ]
        return SearchResponse(results=results, latency_ms=latency_ms)

    def extract(self, urls: list[str]) -> SearchResponse:
        """Full text for URLs a search already surfaced."""
        raw, latency_ms = self._post(f"{_BASE}/extract", {"urls": urls})
        results = [
            SearchResult(
                title=str(r.get("url", "")),
                url=str(r.get("url", "")),
                snippet=str(r.get("raw_content", "")),
            )
            for r in raw.get("results", [])
            if isinstance(r, dict)
        ]
        return SearchResponse(results=results, latency_ms=latency_ms)

    # -- transport ---------------------------------------------------------

    def _post(self, url: str, payload: dict) -> tuple[dict, int]:
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode(),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._key}",
            },
            method="POST",
        )
        started = time.monotonic()
        try:
            with urllib.request.urlopen(request, timeout=self._timeout_s) as response:
                body = json.load(response)
        except urllib.error.HTTPError as exc:
            if exc.code in _QUOTA_STATUSES:
                # The message carries "quota" so `classify()` maps it even if the
                # typed exception is ever lost in translation across a boundary.
                raise ToolQuotaExceeded(
                    f"tavily refused on quota grounds (HTTP {exc.code})"
                ) from exc
            raise
        latency_ms = int((time.monotonic() - started) * 1000)
        return (body if isinstance(body, dict) else {}), latency_ms
