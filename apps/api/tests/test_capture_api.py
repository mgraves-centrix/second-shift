"""The capture API: instants, replay, policy intent, and the capability report."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from secondshift.airlock.capability import build_report
from secondshift.api.app import Context, create_app
from secondshift.api.titles import derive_title
from secondshift.config import (
    CUDA,
    LOCAL_REASONER,
    SPEECH_STACK,
    Capability,
    ProbeResult,
    resolve_profile,
)
from secondshift.db.connection import now_ms
from secondshift.db.ids import new_ulid

TZ = "America/Los_Angeles"


def _probe(local_ok: bool) -> ProbeResult:
    return ProbeResult(
        {
            CUDA: Capability(CUDA, local_ok, "nvidia-smi present" if local_ok else "no CUDA device detected"),
            LOCAL_REASONER: Capability(
                LOCAL_REASONER,
                local_ok,
                "serving 'nemotron-3.5-lightning'" if local_ok
                else "local reasoner endpoint 127.0.0.1:8000 unreachable",
            ),
            SPEECH_STACK: Capability(SPEECH_STACK, local_ok, "importable" if local_ok else "not importable"),
        }
    )


@pytest.fixture
def client_factory(repo, recorder):
    def _make(local_ok: bool = False, is_synthetic: bool = False) -> TestClient:
        resolved = resolve_profile(env={}, probe_result=_probe(local_ok))
        ctx = Context(
            repo=repo,
            recorder=recorder,
            profile=resolved,
            report=build_report(resolved),
            is_synthetic=is_synthetic,
        )
        return TestClient(create_app(ctx))

    return _make


@pytest.fixture
def client(client_factory):
    return client_factory()


def _payload(**kw):
    when = kw.pop("created_at_ms", None) or now_ms()
    body = {
        "id": kw.pop("id", None) or new_ulid(when),
        "created_at_ms": when,
        "captured_tz": TZ,
        "tz_offset_min": -420,
        "policy": "cloud-assisted",
        "text": "a tool that notices when I repeat a mistake",
    }
    body.update(kw)
    return body


class TestCapabilities:
    def test_unavailable_policy_is_marked_not_omitted(self, client_factory):
        body = client_factory(local_ok=False).get("/capabilities").json()
        policies = {p["policy"]: p for p in body["policies"]}
        assert set(policies) == {"local-only", "cloud-assisted"}
        assert policies["local-only"]["available"] is False

    def test_reason_names_the_probe_finding(self, client_factory):
        body = client_factory(local_ok=False).get("/capabilities").json()
        reason = next(p for p in body["policies"] if p["policy"] == "local-only")["reason"]
        assert "endpoint" in reason
        assert reason != "unavailable on this profile"

    def test_available_when_the_local_stack_is_up(self, client_factory):
        body = client_factory(local_ok=True).get("/capabilities").json()
        assert next(p for p in body["policies"] if p["policy"] == "local-only")["available"]


class TestCaptureInstants:
    def test_capture_instant_is_the_clients_not_the_receipt(self, client):
        captured = now_ms() - 8 * 3600 * 1000
        body = client.post("/entries", json=_payload(created_at_ms=captured)).json()
        assert body["created_at_ms"] == captured
        assert body["received_at_ms"] > captured

    def test_future_client_instant_is_accepted(self, client):
        future = now_ms() + 86_400_000
        r = client.post("/entries", json=_payload(created_at_ms=future))
        assert r.status_code == 201
        assert r.json()["created_at_ms"] == future

    def test_identifier_disagreeing_with_instant_is_rejected(self, client):
        when = now_ms()
        body = _payload(created_at_ms=when, id=new_ulid(when - 60_000))
        assert client.post("/entries", json=body).status_code == 422


class TestReplay:
    def test_duplicate_yields_one_row_and_two_successes(self, client, repo):
        body = _payload()
        first = client.post("/entries", json=body)
        second = client.post("/entries", json=body)
        assert first.status_code == 201 and second.status_code == 200
        assert second.json()["duplicate"] is True
        assert len(repo.dispatch_eligible_entries()) == 1

    def test_duplicate_records_no_failure(self, client, conn):
        body = _payload()
        client.post("/entries", json=body)
        client.post("/entries", json=body)
        assert conn.execute("SELECT COUNT(*) n FROM failures").fetchone()["n"] == 0

    def test_divergent_replay_keeps_stored_and_records_it(self, client, repo):
        body = _payload()
        client.post("/entries", json=body)
        changed = dict(body, text="edited before the queue drained")
        response = client.post("/entries", json=changed)
        assert response.json()["text"] == body["text"]
        labels = [e["label"] for e in repo.entry_history(body["id"])]
        assert any("divergent" in label for label in labels)


class TestPolicyIntent:
    def test_local_only_is_stored_intact_on_a_profile_that_cannot_honor_it(
        self, client_factory, repo
    ):
        client = client_factory(local_ok=False)
        body = _payload(policy="local-only")
        assert client.post("/entries", json=body).status_code == 201
        assert repo.get_entry(body["id"])["default_policy"] == "local-only"

    def test_local_only_entry_is_then_quarantined_not_rewritten(
        self, client_factory, repo
    ):
        from secondshift.airlock.quarantine import Quarantine

        client = client_factory(local_ok=False)
        body = _payload(policy="local-only")
        client.post("/entries", json=body)
        resolved = resolve_profile(env={}, probe_result=_probe(False))
        blocked = Quarantine(repo, build_report(resolved)).blocked()
        assert [s.entry_id for s in blocked] == [body["id"]]

    def test_unknown_policy_is_refused(self, client):
        assert client.post("/entries", json=_payload(policy="whatever")).status_code == 422

    def test_the_offer_is_recorded_on_the_entry(self, client_factory, repo):
        client = client_factory(local_ok=False)
        body = _payload()
        client.post("/entries", json=body)
        offered = json.loads(repo.get_entry(body["id"])["offered_capability_json"])
        local = next(p for p in offered["policies"] if p["policy"] == "local-only")
        assert local["available"] is False and "endpoint" in local["reason"]


class TestServerDerivedFields:
    def test_client_cannot_assert_synthetic(self, client):
        response = client.post("/entries", json=_payload(is_synthetic=True))
        assert response.status_code == 422  # extra="forbid"

    def test_synthetic_deployment_marks_its_own_entries(self, client_factory, repo):
        client = client_factory(is_synthetic=True)
        body = _payload()
        client.post("/entries", json=body)
        assert repo.get_entry(body["id"])["is_synthetic"] == 1
        assert repo.dispatch_eligible_entries() == []

    def test_capture_profile_prefers_the_clients(self, client, repo):
        body = _payload(capture_profile="spark")
        client.post("/entries", json=body)
        assert repo.get_entry(body["id"])["capture_profile"] == "spark"

    def test_capture_records_an_event_against_the_entry(self, client, repo):
        body = _payload()
        client.post("/entries", json=body)
        assert len(repo.entry_history(body["id"])) == 1

    def test_no_model_call_is_made_during_capture(self, client, conn):
        client.post("/entries", json=_payload())
        assert conn.execute("SELECT COUNT(*) n FROM model_calls").fetchone()["n"] == 0


class TestTitles:
    def test_first_sentence(self):
        assert derive_title("Build a thing. Then another.") == "Build a thing"

    def test_long_text_truncates_on_a_word_boundary(self):
        title = derive_title("word " * 40)
        assert title.endswith("…") and len(title) <= 73 and not title.endswith("wor…")

    def test_empty_text_has_no_title(self):
        assert derive_title("   ") is None

    def test_derived_at_capture(self, client):
        body = client.post("/entries", json=_payload(text="Ship the capture path. Soon.")).json()
        assert body["title"] == "Ship the capture path"

    def test_explicit_title_wins(self, client):
        body = client.post("/entries", json=_payload(title="Mine")).json()
        assert body["title"] == "Mine"
