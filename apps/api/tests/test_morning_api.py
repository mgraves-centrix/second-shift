"""The morning over HTTP.

Written because the last run shipped `secondshift/morning/` with **no caller**:
no route, no CLI, nothing. The proposal, the roadmap and the prompt all said the
server half was "reachable through the API", and it was not — it was an island
that imported and tested cleanly and that no running system could reach.

`API_LAYER.md`'s scope says "no new routes; a capability adds its own", so these
are this capability's to add, and they are what make that claim true.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from secondshift.airlock.capability import build_report
from secondshift.api.app import Context, create_app
from secondshift.config import resolve_profile
from secondshift.db.connection import now_ms


def _client(repo, recorder, *, is_synthetic: bool = False) -> TestClient:
    resolved = resolve_profile(env={"SECOND_SHIFT_PROFILE": "cloud"})
    return TestClient(
        create_app(
            Context(
                repo=repo,
                recorder=recorder,
                profile=resolved,
                report=build_report(resolved),
                is_synthetic=is_synthetic,
            )
        )
    )


@pytest.fixture
def client(repo, recorder):
    return _client(repo, recorder)


@pytest.fixture
def entry(repo):
    return repo.insert_entry(
        created_at_ms=now_ms(),
        captured_tz="UTC",
        tz_offset_min=0,
        modality="text",
        default_policy="cloud-assisted",
        status="queued",
        capture_profile="spark",
        raw_text="a weekly digest of my voice notes",
    )


@pytest.fixture
def night(repo, entry):
    def _make(*, is_synthetic: bool = False):
        run_id = repo.insert_run(
            entry_id=entry,
            night_of="2026-09-03",
            effective_policy="cloud-assisted",
            policy_source="entry-default",
            compute_profile="spark",
            is_synthetic=is_synthetic,
        )
        for seq, (stage, stat) in enumerate(
            [("brief", "complete"), ("research", "skipped"), ("build", "failed")], 1
        ):
            sid = repo.insert_run_stage(
                run_id=run_id, stage=stage, seq=seq, status="running"
            )
            repo.complete_run_stage(sid, status=stat)
        repo.close_run(run_id, outcome="degraded", furthest_stage="brief")
        return run_id

    return _make


class TestTheMorningIsReachable:
    def test_the_route_exists(self, client):
        """The gap this file was written for: it did not."""
        assert client.get("/morning").status_code == 200

    def test_an_empty_morning_is_a_briefing_not_an_error(self, client):
        """Principle 3's shape at the HTTP boundary: nothing to report is still
        a briefing, never a 404 or an error body."""
        body = client.get("/morning").json()

        assert body == {"nights": [], "questions": [], "interviewer_error": None}

    def test_a_night_is_reported_with_its_stages(self, client, night):
        night()

        body = client.get("/morning").json()

        assert len(body["nights"]) == 1
        statuses = {s["stage"]: s["status"] for s in body["nights"][0]["stages"]}
        assert statuses == {"brief": "complete", "research": "skipped", "build": "failed"}

    def test_fetching_the_briefing_does_not_consume_it(
        self, client, repo, entry, night
    ):
        """A GET that advanced its own delta would lose a morning because
        somebody opened the app while walking. Asserted over HTTP because that
        is where the mistake would be easiest to make.

        The open decision is load-bearing: an earlier version of this test had
        none, so a mutation that consumed every unanswered decision on render
        left it green — there was nothing to consume. A test that cannot reach
        the mechanism it names is testing the absence of data.
        """
        night()
        repo.insert_decision(
            entry_id=entry, question="q", rationale="r", status="open"
        )

        first = client.get("/morning").json()
        second = client.get("/morning").json()

        assert len(first["nights"]) == 1
        assert len(second["nights"]) == 1
        assert len(second["questions"]) == 1, "rendering consumed the question"

    def test_an_open_question_is_carried_with_its_rationale(self, client, repo, entry):
        repo.insert_decision(
            entry_id=entry,
            question="Do you read it on a phone?",
            rationale="two shapes, could not choose",
            status="open",
        )

        body = client.get("/morning").json()

        assert body["questions"][0]["question"] == "Do you read it on a phone?"
        assert body["questions"][0]["rationale"] == "two shapes, could not choose"

    def test_the_egress_warning_travels_on_the_question(self, client, repo, entry):
        """So a screen cannot forget to say it. A warning that lives only in a
        component is one the next component does not inherit."""
        repo.insert_decision(
            entry_id=entry, question="q", rationale="r", status="open"
        )

        body = client.get("/morning").json()

        assert "will_leave_the_machine" in body["questions"][0]


class TestAnsweringOverHttp:
    @pytest.fixture
    def decision(self, repo, entry):
        return repo.insert_decision(
            entry_id=entry,
            question="Do you read it on a phone?",
            rationale="two shapes",
            status="open",
        )

    def test_answering_records_the_decision(self, client, repo, decision):
        response = client.post(
            f"/decisions/{decision}/answer",
            json={"answer": "phone", "status": "decided"},
        )

        assert response.status_code == 200
        row = repo.connection.execute(
            "SELECT * FROM decisions WHERE id = ?", (decision,)
        ).fetchone()
        assert row["answer"] == "phone"
        assert row["answer_modality"] == "text"

    def test_answering_an_unknown_question_is_404(self, client):
        """An answer to a question nobody asked has nothing to mean."""
        response = client.post(
            "/decisions/no-such-id/answer",
            json={"answer": "whatever", "status": "decided"},
        )

        assert response.status_code == 404

    def test_answering_twice_is_refused(self, client, decision):
        client.post(
            f"/decisions/{decision}/answer",
            json={"answer": "first", "status": "decided"},
        )

        second = client.post(
            f"/decisions/{decision}/answer",
            json={"answer": "second", "status": "decided"},
        )

        assert second.status_code == 404

    def test_an_unknown_status_is_rejected_by_the_schema(self, client, decision):
        """The state machine is the schema's, not free text."""
        response = client.post(
            f"/decisions/{decision}/answer",
            json={"answer": "x", "status": "sort-of-decided"},
        )

        assert response.status_code == 422

    def test_answering_advances_the_boundary_over_http(self, client, night, decision):
        night()
        assert len(client.get("/morning").json()["nights"]) == 1

        client.post(
            f"/decisions/{decision}/answer",
            json={"answer": "phone", "status": "decided"},
        )

        assert client.get("/morning").json()["nights"] == []


class TestNoChatInterface:
    """`NOT_BUILDING.md` excludes a general chat interface by name, and the
    prompt calls it the single most likely way this capability goes wrong. The
    guard is the URL shape: every answer route carries a decision id."""

    def test_there_is_no_route_that_takes_an_instruction(self, client):
        paths = {
            r.path for r in client.app.routes if hasattr(r, "path")
        }

        for suspicious in ("/chat", "/message", "/ask", "/interview"):
            assert suspicious not in paths

    def test_every_answer_route_carries_a_decision_id(self, client):
        answering = [
            r.path
            for r in client.app.routes
            if hasattr(r, "path") and "answer" in r.path
        ]

        assert answering == ["/decisions/{decision_id}/answer"]

    def test_the_answer_body_has_no_free_text_field_beyond_the_answer(self):
        from secondshift.api.schemas import AnswerRequest

        assert set(AnswerRequest.model_fields) == {"answer", "status", "modality"}


class TestTheJudgeInstanceSeesItsSeededNights:
    """Principle 5: the judge deployment runs this same code over synthetic
    rows. A briefing that filtered them would show a judge an empty morning —
    which is the one thing it must not do.

    `include_synthetic` had no caller and no test until this file; it is set
    from the deployment's own flag, never from a request.
    """

    def test_a_synthetic_night_is_hidden_from_the_personal_instance(
        self, repo, recorder, night
    ):
        night(is_synthetic=True)

        body = _client(repo, recorder, is_synthetic=False).get("/morning").json()

        assert body["nights"] == []

    def test_a_synthetic_night_is_shown_on_the_judge_instance(
        self, repo, recorder, night
    ):
        night(is_synthetic=True)

        body = _client(repo, recorder, is_synthetic=True).get("/morning").json()

        assert len(body["nights"]) == 1

    def test_the_flag_comes_from_the_deployment_not_the_request(self, client, night):
        """Server-derived, never accepted from a request — the same rule capture
        already follows, and for the same reason."""
        night(is_synthetic=True)

        body = client.get("/morning?include_synthetic=true").json()

        assert body["nights"] == []
