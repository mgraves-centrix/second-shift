"""The research stage: the only place the system talks to the open internet.

The order of the guards here is the design. `local-only` is refused **before a
query is constructed**, not before the call is made — under that policy the raw
text is never even tokenized, so there is no window in which a query built from
a private idea exists in memory waiting for a check further down.

Nothing in this module fabricates a result, and nothing falls back to raw text.
A query too thin to search is a reason to skip, never a reason to try harder.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..airlock.policy import Policy
from ..airlock.redact import build_query
from ..providers.tavily import TavilyNotConfigured, TavilyProvider
from ..telemetry.recorder import Recorder

#: Reasons the stage records when it does not search. Each is written to the
#: stage row, so a night that did no research says which of these it was — the
#: three are not interchangeable and a morning should not have to guess.
LOCAL_ONLY = "local-only: a search carries the idea off the machine"
NO_CREDENTIAL = "no search credential is configured"
NOTHING_SEARCHABLE = "nothing searchable survived redaction"

#: Below this many terms, the entry was contact details or grammar rather than
#: an idea. Skipped rather than searched: `test_an_entry_that_is_only_contact_
#: details_yields_almost_nothing` pins the case this exists for.
_MIN_TERMS = 2


@dataclass(frozen=True, slots=True)
class ResearchResult:
    """What the stage did. `query` is the redacted one or nothing."""

    searched: bool
    reason: str | None = None
    query: str = ""
    result_count: int = 0
    credits: float = 0.0
    digest: str = ""


def run_research(
    recorder: Recorder,
    *,
    policy: str,
    entry_text: str,
    provider: TavilyProvider | None = None,
    max_results: int = 5,
) -> ResearchResult:
    """Search for what this idea needs, or say why nothing was searched.

    Raises nothing on a missing credential or an unsearchable entry — those are
    skips with reasons. A quota refusal *does* propagate, because the caller
    turns it into a typed failure and a degraded night, and swallowing it here
    would hide a spend limit behind an empty digest.
    """
    # First, and before the text is touched at all. A search carries the idea
    # off the machine as surely as a completion does, and the synthetic
    # generator has asserted this behavior since before there was a real path.
    if policy == str(Policy.LOCAL_ONLY):
        return ResearchResult(searched=False, reason=LOCAL_ONLY)

    if provider is None:
        try:
            provider = TavilyProvider()
        except TavilyNotConfigured:
            return ResearchResult(searched=False, reason=NO_CREDENTIAL)

    query = build_query(entry_text)
    if len(query.split()) < _MIN_TERMS:
        # Never a fallback to the raw text. That single move would undo the
        # whole module, and it is the shape a well-meaning later change takes.
        return ResearchResult(searched=False, reason=NOTHING_SEARCHABLE)

    response = provider.search(query, max_results=max_results)

    # Only the redacted query is ever handed to the recorder. There is no
    # parameter on `record_tool_call` that would take the raw text, and this is
    # the only place a query reaches telemetry.
    recorder.record_tool_call(
        tool=provider.tool,
        endpoint="search",
        policy=policy,
        query_redacted=query,
        credits=response.credits,
        result_count=len(response.results),
        latency_ms=response.latency_ms,
        cached=response.cached,
        outcome="success",
    )
    return ResearchResult(
        searched=True,
        query=query,
        result_count=len(response.results),
        credits=response.credits,
        digest=_digest(response.results),
    )


def _digest(results) -> str:
    """The search results as text an agent can read.

    Not a summary — summarizing is an agent's turn and a model call, not a tool
    call. This is the raw material, cited, so the researcher's brief can name
    where each claim came from.
    """
    return "\n\n".join(
        f"### {r.title}\n{r.url}\n\n{r.snippet}" for r in results if r.url
    )
