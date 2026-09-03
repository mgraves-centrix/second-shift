"""The research stage: what it refuses, what it records, and what never leaves.

The stub lives here and not in `providers/` on purpose. An importable object
that returns convincing search results could put invented rows into
`tool_calls`, and the credit curve is a scored measurement — so the shipped
package has no such object, the same property `EchoReasoner` has by returning
its own input.
"""

from __future__ import annotations

import pytest

from secondshift.db.connection import now_ms
from secondshift.night.research import (
    LOCAL_ONLY,
    NO_CREDENTIAL,
    NOTHING_SEARCHABLE,
    run_research,
)
from secondshift.providers.tavily import (
    SearchResponse,
    SearchResult,
    TavilyNotConfigured,
    TavilyProvider,
)
from secondshift.telemetry.failures import ToolQuotaExceeded

#: The entry every test in this module searches from. Carries a client name, a
#: codename and distinctive phrasing, so a leak has somewhere to show up.
ENTRY = (
    "Work out how Northwind Health should stage the Halyard rollout without "
    "burning the support team out."
)


class StubTavily:
    """Visibly inert. Returns fixed results that could never be mistaken for a
    real search, and records what it was asked so a test can inspect it."""

    tool = "tavily"

    def __init__(self, *, raises: Exception | None = None, credits: float = 1.0) -> None:
        self.queries: list[str] = []
        self._raises = raises
        self._credits = credits

    def search(self, query: str, *, max_results: int = 5) -> SearchResponse:
        self.queries.append(query)
        if self._raises is not None:
            raise self._raises
        return SearchResponse(
            results=[
                SearchResult("STUB RESULT", "https://example.invalid/1", "stub body"),
                SearchResult("STUB RESULT", "https://example.invalid/2", "stub body"),
            ],
            latency_ms=12,
            credits=self._credits,
        )


@pytest.fixture
def stub():
    return StubTavily()


class TestALocalOnlyRunMakesNoCall:
    def test_it_writes_zero_tool_calls(self, repo, recorder, stub):
        """The count, not the shape. Not a redacted call — none."""
        run_research(recorder, policy="local-only", entry_text=ENTRY, provider=stub)

        rows = list(repo.connection.execute("SELECT * FROM tool_calls"))
        assert rows == []

    def test_the_provider_is_never_reached(self, recorder, stub):
        run_research(recorder, policy="local-only", entry_text=ENTRY, provider=stub)

        assert stub.queries == []

    def test_no_query_is_even_constructed(self, recorder, stub, monkeypatch):
        """The refusal is above query construction, so under `local-only` the
        raw text is never tokenized. There is no window in which a query built
        from a private idea exists waiting for a check further down."""
        from secondshift.night import research

        def refuse(text):
            raise AssertionError("build_query ran under local-only")

        monkeypatch.setattr(research, "build_query", refuse)

        result = run_research(
            recorder, policy="local-only", entry_text=ENTRY, provider=stub
        )
        assert result.reason == LOCAL_ONLY

    def test_the_reason_is_recorded_and_specific(self, recorder, stub):
        result = run_research(
            recorder, policy="local-only", entry_text=ENTRY, provider=stub
        )

        assert not result.searched
        assert "off the machine" in result.reason


class TestWhatReachesTavily:
    def test_the_query_carries_no_name_or_codename(self, recorder, stub):
        run_research(
            recorder, policy="cloud-assisted", entry_text=ENTRY, provider=stub
        )

        sent = stub.queries[0].lower()
        assert "northwind" not in sent
        assert "halyard" not in sent

    def test_the_query_carries_no_distinctive_phrase(self, recorder, stub):
        run_research(
            recorder, policy="cloud-assisted", entry_text=ENTRY, provider=stub
        )

        assert "burning the support team" not in stub.queries[0].lower()

    def test_the_raw_entry_is_never_sent(self, recorder, stub):
        run_research(
            recorder, policy="cloud-assisted", entry_text=ENTRY, provider=stub
        )

        assert stub.queries[0] != ENTRY
        assert ENTRY.lower() not in stub.queries[0].lower()

    def test_what_is_sent_is_readable_beside_its_entry(self, recorder, stub):
        """The comparison the prompt asks to be the test. Printed on failure so
        a person can judge it rather than trust an assertion."""
        run_research(
            recorder, policy="cloud-assisted", entry_text=ENTRY, provider=stub
        )
        sent = stub.queries[0]

        assert sent, f"entry: {ENTRY!r}\nquery: {sent!r}"
        assert set(sent.split()) <= {w.strip(".,?").lower() for w in ENTRY.split()}


class TestTheRawTextIsNowhereInTheDatabase:
    def test_a_distinctive_phrase_appears_in_entries_and_nowhere_else(
        self, repo, recorder, stub
    ):
        """Grep the whole database, not just `tool_calls`. The raw query must
        not reach events, payloads, or any other table."""
        entry_id = repo.insert_entry(
            created_at_ms=now_ms(),
            captured_tz="UTC",
            tz_offset_min=0,
            modality="text",
            default_policy="cloud-assisted",
            status="queued",
            capture_profile="cloud",
            raw_text=ENTRY,
        )
        run_research(
            recorder, policy="cloud-assisted", entry_text=ENTRY, provider=stub
        )

        needle = "burning the support team"
        found: list[str] = []
        tables = [
            r["name"]
            for r in repo.connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        ]
        for table in tables:
            columns = [
                c["name"]
                for c in repo.connection.execute(f"PRAGMA table_info({table})")
            ]
            for column in columns:
                hits = repo.connection.execute(
                    f"SELECT COUNT(*) n FROM {table} "
                    f"WHERE CAST({column} AS TEXT) LIKE ?",
                    (f"%{needle}%",),
                ).fetchone()["n"]
                if hits:
                    found.append(f"{table}.{column}")

        assert found == ["entries.raw_text"], found
        assert entry_id


class TestRecordingTheCall:
    def test_the_stored_query_is_the_redacted_one(self, repo, recorder, stub):
        result = run_research(
            recorder, policy="cloud-assisted", entry_text=ENTRY, provider=stub
        )

        row = repo.connection.execute("SELECT * FROM tool_calls").fetchone()
        assert row["query_redacted"] == result.query
        assert row["query_redacted"] == stub.queries[0]

    def test_the_call_records_the_policy_it_ran_under(self, repo, recorder, stub):
        run_research(
            recorder, policy="cloud-assisted", entry_text=ENTRY, provider=stub
        )

        row = repo.connection.execute("SELECT * FROM tool_calls").fetchone()
        assert row["policy"] == "cloud-assisted"

    def test_result_count_and_credits_are_recorded(self, repo, recorder, stub):
        run_research(
            recorder, policy="cloud-assisted", entry_text=ENTRY, provider=stub
        )

        row = repo.connection.execute("SELECT * FROM tool_calls").fetchone()
        assert row["result_count"] == 2
        assert row["credits"] == 1.0
        assert row["outcome"] == "success"

    def test_a_run_s_spend_is_the_sum_of_its_calls(self, repo, recorder):
        for credits in (1.0, 2.0, 0.5):
            run_research(
                recorder,
                policy="cloud-assisted",
                entry_text=ENTRY,
                provider=StubTavily(credits=credits),
            )

        total = repo.connection.execute(
            "SELECT SUM(credits) s FROM tool_calls"
        ).fetchone()["s"]
        assert total == 3.5


class TestSkipsThatAreNotFailures:
    def test_no_credential_skips_with_a_reason_and_no_row(self, repo, recorder):
        """The state this shipped in. No fabricated row, and the reason says so
        rather than looking like a search that found nothing."""
        result = run_research(
            recorder, policy="cloud-assisted", entry_text=ENTRY, provider=None
        )

        assert not result.searched
        assert result.reason == NO_CREDENTIAL
        assert list(repo.connection.execute("SELECT * FROM tool_calls")) == []

    def test_an_unsearchable_entry_skips_rather_than_falling_back(
        self, repo, recorder, stub
    ):
        """The one move that would undo the whole module: falling back toward
        the raw text when redaction leaves too little."""
        result = run_research(
            recorder,
            policy="cloud-assisted",
            entry_text="Reach me at person@example.com or box.tailnet-name.ts.net.",
            provider=stub,
        )

        assert result.reason == NOTHING_SEARCHABLE
        assert stub.queries == []
        assert list(repo.connection.execute("SELECT * FROM tool_calls")) == []


class TestQuotaDegradesRatherThanEnds:
    def test_a_quota_refusal_propagates_as_its_typed_exception(self, recorder):
        """Propagated, not swallowed: the caller turns it into a typed failure
        and a degraded night. Swallowing it here would hide a spend limit
        behind an empty digest."""
        stub = StubTavily(raises=ToolQuotaExceeded("tavily quota exhausted"))

        with pytest.raises(ToolQuotaExceeded):
            run_research(
                recorder, policy="cloud-assisted", entry_text=ENTRY, provider=stub
            )

    def test_the_taxonomy_maps_it_to_tool_quota(self):
        from secondshift.telemetry.failures import FailureType, classify

        assert classify(ToolQuotaExceeded("quota exhausted")) is FailureType.TOOL_QUOTA

    def test_a_quota_http_status_becomes_the_typed_exception(self):
        """Both statuses Tavily uses, so a 402 is not silently a generic error."""
        from secondshift.providers.tavily import _QUOTA_STATUSES

        assert _QUOTA_STATUSES == {402, 429}


class TestNothingFabricatesResults:
    def test_the_provider_refuses_without_a_credential(self, monkeypatch):
        monkeypatch.delenv("TAVILY_API_KEY", raising=False)

        with pytest.raises(TavilyNotConfigured, match="not set"):
            TavilyProvider()

    def test_the_refusal_explains_why_there_is_no_offline_mode(self, monkeypatch):
        monkeypatch.delenv("TAVILY_API_KEY", raising=False)

        with pytest.raises(TavilyNotConfigured) as caught:
            TavilyProvider()

        assert "indistinguishable" in str(caught.value)

    def test_the_shipped_package_contains_no_result_fabricator(self):
        """The stub is in this test module. Nothing importable from
        `providers/` can put invented rows into `tool_calls`."""
        from pathlib import Path

        from secondshift.providers import tavily

        source = Path(tavily.__file__).read_text()
        assert "class StubTavily" not in source
        assert "example.invalid" not in source


class TestTheExtractEndpoint:
    """`extract` shipped with no test at all — a whole public method on the one
    provider that talks to the internet. Exercised here against a fake HTTP
    transport rather than the network, so the suite stays hermetic and spends
    nothing."""

    @pytest.fixture
    def provider(self, monkeypatch):
        from secondshift.providers.tavily import TavilyProvider

        monkeypatch.setenv("TAVILY_API_KEY", "not-a-real-key")
        return TavilyProvider()

    def _fake_post(self, monkeypatch, payload: dict, captured: dict):
        from secondshift.providers import tavily

        def _post(self, url, body):
            captured["url"] = url
            captured["body"] = body
            return payload, 7

        monkeypatch.setattr(tavily.TavilyProvider, "_post", _post)

    def test_it_calls_the_extract_endpoint(self, provider, monkeypatch):
        captured: dict = {}
        self._fake_post(monkeypatch, {"results": []}, captured)

        provider.extract(["https://example.invalid/a"])

        assert captured["url"].endswith("/extract")
        assert captured["body"] == {"urls": ["https://example.invalid/a"]}

    def test_it_returns_the_extracted_text(self, provider, monkeypatch):
        captured: dict = {}
        self._fake_post(
            monkeypatch,
            {"results": [{"url": "https://example.invalid/a", "raw_content": "body"}]},
            captured,
        )

        response = provider.extract(["https://example.invalid/a"])

        assert [r.snippet for r in response.results] == ["body"]

    def test_a_malformed_result_is_skipped_rather_than_crashing(
        self, provider, monkeypatch
    ):
        """The provider reads someone else's JSON. A shape it did not expect
        must not take the night down."""
        captured: dict = {}
        self._fake_post(monkeypatch, {"results": ["not a dict", {"url": "u"}]}, captured)

        response = provider.extract(["https://example.invalid/a"])

        assert len(response.results) == 1

    def test_search_and_extract_use_the_recorded_endpoint_names(
        self, provider, monkeypatch
    ):
        """The URL called and the string written to `tool_calls.endpoint` come
        from the same constants. They were two separate literals until an audit
        found them, which is one edit away from a row that says `search` about a
        call that went somewhere else."""
        from secondshift.providers.tavily import EXTRACT, SEARCH

        captured: dict = {}
        self._fake_post(monkeypatch, {"results": []}, captured)

        provider.search("a query")
        assert captured["url"].endswith(f"/{SEARCH}")

        provider.extract(["https://example.invalid/a"])
        assert captured["url"].endswith(f"/{EXTRACT}")
