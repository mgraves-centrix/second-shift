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


def served_paths(client: TestClient) -> set[str]:
    """Every path the application actually serves.

    Read from the generated schema rather than from `app.routes`, because since
    FastAPI 0.141 an included router is stored in that list as one lazy proxy
    object and the routes behind it are not. Three guards in this file read it
    as a flat list of paths. When the layer was split into one router per
    capability, one of them failed — and the other two, which assert an
    *absence*, would have gone on passing against an empty set. Those two are
    the Privacy Airlock and the scope boundary expressed as URL shape, so the
    quiet failure was the expensive one.
    """
    return set(client.app.openapi()["paths"])


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

    def test_the_egress_warning_travels_on_the_question(self, client, repo):
        """So a screen cannot forget to say it. A warning that lives only in a
        component is one the next component does not inherit.

        This asserted `"will_leave_the_machine" in body["questions"][0]` until
        3 Sep, which a field that is permanently `false` satisfies — and it was
        permanently `false`, because `_open_questions` never set it. A test that
        checks a key is present is a test of the response model, not of the
        feature the response model carries.
        """
        local = repo.insert_entry(
            created_at_ms=now_ms(),
            captured_tz="UTC",
            tz_offset_min=0,
            modality="text",
            default_policy="local-only",
            status="queued",
            capture_profile="spark",
            raw_text="the one I would not paste into a chat box",
        )
        repo.insert_decision(
            entry_id=local, question="q", rationale="r", status="open"
        )

        body = client.get("/morning").json()

        assert body["questions"][0]["will_leave_the_machine"] is True

    def test_a_cloud_assisted_question_carries_no_warning(
        self, client, repo, entry
    ):
        """The `entry` fixture is `cloud-assisted`: the idea has already left,
        so there is nothing an answer could authorize."""
        repo.insert_decision(
            entry_id=entry, question="q", rationale="r", status="open"
        )

        body = client.get("/morning").json()

        assert body["questions"][0]["will_leave_the_machine"] is False


class TestReadingAnArtifactBack:
    """"Idea in, artifact out" is the product's whole claim, and until 19 Sep the
    artifact could not be opened: the night wrote files and nothing served them.
    """

    @pytest.fixture
    def written(self, repo, entry, tmp_path, monkeypatch):
        from secondshift.artifacts.store import ENV_ARTIFACTS

        monkeypatch.setenv(ENV_ARTIFACTS, str(tmp_path))
        run_id = repo.insert_run(
            entry_id=entry,
            night_of="2026-09-19",
            effective_policy="local-only",
            policy_source="entry-default",
            compute_profile="spark",
        )
        body = "# A brief\n\nThe shape that survives contact.\n"
        target = tmp_path / "2026-09-19" / run_id / "brief.md"
        target.parent.mkdir(parents=True)
        target.write_text(body)
        artifact_id = repo.insert_artifact(
            run_id=run_id,
            entry_id=entry,
            stage="brief",
            kind="brief",
            path=f"2026-09-19/{run_id}/brief.md",
            content_sha="x" * 64,
            artifact_bytes=len(body),
        )
        return artifact_id, body, tmp_path

    def test_an_artifact_is_returned_by_identity(self, client, written):
        artifact_id, body, _ = written

        response = client.get(f"/artifacts/{artifact_id}")

        assert response.status_code == 200
        assert response.text == body
        assert response.headers["content-type"].startswith("text/markdown")

    def test_an_unknown_artifact_is_refused(self, client):
        assert client.get("/artifacts/01JNOTHINGHERE").status_code == 404

    def test_a_row_whose_file_is_missing_is_a_404_not_an_empty_200(
        self, client, written
    ):
        """The seeded night writes rows with no bytes behind them. An empty 200
        would present that as an artifact containing nothing, which is a
        different and worse claim than "it is not there"."""
        artifact_id, _, root = written
        (root / "2026-09-19").rename(root / "moved-away")

        response = client.get(f"/artifacts/{artifact_id}")

        assert response.status_code == 404
        assert response.content != b""

    def test_a_row_cannot_escape_the_artifact_root(
        self, client, repo, entry, written
    ):
        """A stored path is data. This is the one place it becomes a filesystem
        read, so the resolved file has to be under the root whatever the row
        says."""
        artifact_id, _, root = written
        escaped = repo.insert_artifact(
            run_id=repo.get_artifact(artifact_id)["run_id"],
            entry_id=entry,
            stage="brief",
            kind="brief",
            path="../../../../etc/passwd",
            content_sha="y" * 64,
            artifact_bytes=1,
        )

        assert client.get(f"/artifacts/{escaped}").status_code == 404

    def test_nothing_travels_with_the_artifact(self, client, written, repo):
        """`model_call_payloads` holds raw local-only content and the schema
        says it must never reach a judge deployment.

        Asserted behaviorally. The first version of this test grepped the
        route's source for the word "payload" — which its own comment explaining
        the exclusion contains, so the test forbade documenting the rule it was
        checking. A test that fails on a comment is testing the comment.
        """
        artifact_id, body, _ = written

        response = client.get(f"/artifacts/{artifact_id}")

        assert response.content == body.encode(), (
            "something was added to the artifact's bytes on the way out"
        )

    def test_no_route_serves_a_payload(self, client):
        """The absence is structural: there is nowhere for that content to go."""
        assert not [p for p in served_paths(client) if "payload" in p]


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

    def test_resubmitting_the_same_answer_is_not_an_error(self, client, repo, decision):
        """A phone that lost the response to an answer the server recorded
        retries, and the retry must succeed. It got a 404, which the screen
        reads as "not recorded", so the person could never get past the
        question they had already answered."""
        body = {"answer": "phone", "status": "queued-for-tonight"}
        first = client.post(f"/decisions/{decision}/answer", json=body)

        retry = client.post(f"/decisions/{decision}/answer", json=body)

        assert retry.status_code == 200
        assert retry.json() == first.json()

    def test_answering_twice_is_refused(self, client, decision):
        client.post(
            f"/decisions/{decision}/answer",
            json={"answer": "first", "status": "decided"},
        )

        second = client.post(
            f"/decisions/{decision}/answer",
            json={"answer": "second", "status": "decided"},
        )

        # A conflict rather than not-found: the question exists and was
        # answered differently, which is not the same claim as "no such question".
        assert second.status_code == 409

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

    def test_the_surface_is_not_empty(self, client):
        """The two tests below assert that nothing matches.

        That is worth nothing unless there was something to match, and this is
        the assumption that quietly stopped holding when the layer was split.
        """
        assert "/decisions/{decision_id}/answer" in served_paths(client)

    def test_there_is_no_route_that_takes_an_instruction(self, client):
        paths = served_paths(client)

        for suspicious in ("/chat", "/message", "/ask", "/interview"):
            assert suspicious not in paths

    def test_every_answer_route_carries_a_decision_id(self, client):
        answering = [p for p in served_paths(client) if "answer" in p]

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
