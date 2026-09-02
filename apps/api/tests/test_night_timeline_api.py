"""Reading a recorded night back.

Exercised against a real generated night rather than a hand-built fixture. Every
claim here is a claim about the shape the generator actually produces — an event
with no invocation, an event whose lane differs from its producer's role, a
duration too short to draw — and a fixture written to suit the assertions would
prove none of them.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from secondshift.airlock.capability import build_report
from secondshift.api.app import Context, create_app
from secondshift.config import resolve_profile

_SEED_PACKAGE = Path(__file__).resolve().parents[3] / "packages" / "seed"
if str(_SEED_PACKAGE) not in sys.path:
    sys.path.insert(0, str(_SEED_PACKAGE))

from secondshift_seed import generate_night  # noqa: E402

SEED = 42


@pytest.fixture
def night(repo):
    return generate_night(repo, seed=SEED)


@pytest.fixture
def client(repo, recorder):
    resolved = resolve_profile(env={"SECOND_SHIFT_PROFILE": "cloud"})
    return TestClient(
        create_app(
            Context(
                repo=repo,
                recorder=recorder,
                profile=resolved,
                report=build_report(resolved),
                is_synthetic=False,
            )
        )
    )


class TestRunListing:
    def test_a_recorded_night_is_listed(self, client, night):
        runs = client.get("/runs").json()
        assert [r["id"] for r in runs] == [night.run_id]

    def test_every_run_says_whether_it_is_synthetic(self, client, night):
        """A generated night is shown, and marked. Hiding it leaves nothing."""
        assert client.get("/runs").json()[0]["is_synthetic"] is True

    def test_the_listing_carries_the_frame_the_night_spans(self, client, night, repo):
        run = client.get("/runs").json()[0]
        events = repo.timeline(night.run_id)
        assert run["first_event_ms"] == events[0]["ts_ms"]
        assert run["event_count"] == len(events)

    def test_the_frame_ends_after_the_longest_bar_not_at_the_last_start(
        self, client, night, repo
    ):
        """A bar that starts near the end still finishes inside the night.

        In this night the longest bar begins more than an hour before the last
        event starts and runs past it. A frame taken from the last start would
        draw it beyond the edge of its own timeline.
        """
        run = client.get("/runs").json()[0]
        events = repo.timeline(night.run_id)
        last_start = max(e["ts_ms"] for e in events)
        last_end = max(e["ts_ms"] + (e["duration_ms"] or 0) for e in events)
        assert last_end > last_start, "this night is expected to have an overhang"
        assert run["last_event_end_ms"] == last_end

    def test_the_listing_carries_the_zone_the_idea_was_captured_in(
        self, client, night, repo
    ):
        """The night renders in its own local framing, not the server's."""
        run = client.get("/runs").json()[0]
        entry = repo.connection.execute(
            "SELECT captured_tz, tz_offset_min FROM entries WHERE id = "
            "(SELECT entry_id FROM runs WHERE id = ?)",
            (night.run_id,),
        ).fetchone()
        assert run["captured_tz"] == entry["captured_tz"]
        assert run["tz_offset_min"] == entry["tz_offset_min"]

    def test_no_runs_is_an_empty_list_not_an_error(self, client):
        assert client.get("/runs").json() == []


class TestTimeline:
    def test_the_whole_night_arrives_at_once(self, client, night, repo):
        body = client.get(f"/runs/{night.run_id}/timeline").json()
        assert len(body["events"]) == len(repo.timeline(night.run_id))
        assert len(body["events"]) > 1000

    def test_no_event_carries_a_payload(self, client, night):
        """The property, enforced by what the response cannot express."""
        body = client.get(f"/runs/{night.run_id}/timeline").json()
        assert body["events"]
        for event in body["events"]:
            assert "payload" not in event
            assert "payload_json" not in event

    def test_lanes_are_the_lanes_the_events_recorded(self, client, night, repo):
        body = client.get(f"/runs/{night.run_id}/timeline").json()
        assert body["lanes"] == sorted({e["lane"] for e in repo.timeline(night.run_id)})

    def test_an_event_with_no_invocation_still_has_a_lane(self, client, night):
        """Stage boundaries have no producer. They must not be dropped."""
        body = client.get(f"/runs/{night.run_id}/timeline").json()
        orphans = [e for e in body["events"] if e["agent_invocation_id"] is None]
        assert orphans, "the generated night is expected to contain stage boundaries"
        assert all(e["lane"] in body["lanes"] for e in orphans)

    def test_a_lane_whose_only_event_has_no_invocation_still_appears(
        self, client, night, repo
    ):
        """The sharp case, which the generated night does not contain.

        Every lane there happens to hold at least one event with an invocation,
        so a lane set built by joining would still look right. A lane whose only
        event is a stage boundary is where that goes wrong, and it is exactly
        what the schema's `lane` column exists to survive.
        """
        first = repo.timeline(night.run_id)[0]["ts_ms"]
        repo.insert_event(
            run_id=night.run_id,
            agent_invocation_id=None,
            lane="watchdog",
            kind="note",
            label="nothing produced this",
            ts_ms=first + 1,
            is_synthetic=True,
        )

        body = client.get(f"/runs/{night.run_id}/timeline").json()
        assert "watchdog" in body["lanes"]
        assert any(e["lane"] == "watchdog" for e in body["events"])

    def test_a_lane_may_differ_from_its_producers_role(self, client, night, repo):
        """Lane is a decision recorded at write time, not a join to `agents`."""
        divergent = repo.connection.execute(
            "SELECT COUNT(*) n FROM events e "
            "JOIN agent_invocations i ON i.id = e.agent_invocation_id "
            "JOIN agents a ON a.id = i.agent_id "
            "WHERE e.run_id = ? AND e.lane != a.role",
            (night.run_id,),
        ).fetchone()["n"]
        assert divergent > 0, "the night is expected to exercise this divergence"

        body = client.get(f"/runs/{night.run_id}/timeline").json()
        by_id = {e["id"]: e for e in body["events"]}
        for row in repo.connection.execute(
            "SELECT e.id, e.lane FROM events e "
            "JOIN agent_invocations i ON i.id = e.agent_invocation_id "
            "JOIN agents a ON a.id = i.agent_id "
            "WHERE e.run_id = ? AND e.lane != a.role",
            (night.run_id,),
        ):
            assert by_id[row["id"]]["lane"] == row["lane"]

    def test_the_invocation_tree_carries_parentage_and_depth(self, client, night):
        body = client.get(f"/runs/{night.run_id}/timeline").json()
        nodes = body["invocations"]
        assert nodes
        assert max(n["depth"] for n in nodes) >= 2
        ids = {n["id"] for n in nodes}
        for node in nodes:
            assert node["parent_invocation_id"] in ids or node["parent_invocation_id"] is None

    def test_events_arrive_in_time_order(self, client, night):
        stamps = [e["ts_ms"] for e in client.get(f"/runs/{night.run_id}/timeline").json()["events"]]
        assert stamps == sorted(stamps)

    def test_an_unknown_run_is_not_an_empty_night(self, client, night):
        """An empty night is a real thing. A missing one is a different thing."""
        response = client.get("/runs/01ABCDEFGHJKMNPQRSTVWXYZ00/timeline")
        assert response.status_code == 404
        assert "unknown run" in response.json()["detail"]


class TestStagesReachTheClient:
    """`runs.outcome` is null on every recorded run — nothing closes a run yet.

    A night that stopped part-way says so through its stages or not at all, and
    "no empty mornings" is a query over exactly this table.
    """

    def test_the_timeline_carries_what_each_stage_reached(self, client, night, repo):
        stages = client.get(f"/runs/{night.run_id}/timeline").json()["stages"]
        assert [s["stage"] for s in stages] == [
            r["stage"] for r in repo.stages_for_run(night.run_id)
        ]
        assert [s["seq"] for s in stages] == sorted(s["seq"] for s in stages)

    def test_a_stage_still_running_is_visible_as_running(self, client, night):
        """The generated night deliberately leaves its last stage open."""
        stages = client.get(f"/runs/{night.run_id}/timeline").json()["stages"]
        assert any(s["status"] == "running" for s in stages)
        assert any(s["status"] == "complete" for s in stages)

    def test_the_run_row_alone_would_have_said_nothing(self, client, night, repo):
        """The reason stages are carried: the run's own verdict is empty."""
        run = repo.get_run(night.run_id)
        assert run["outcome"] is None and run["ended_at_ms"] is None
        assert client.get(f"/runs/{night.run_id}/timeline").json()["stages"]


class TestEventDetail:
    def _first(self, client, night, predicate):
        for event in client.get(f"/runs/{night.run_id}/timeline").json()["events"]:
            if predicate(event):
                return event
        raise AssertionError("the generated night did not contain a matching event")

    def test_detail_carries_the_payload_the_timeline_withheld(self, client, night):
        event = self._first(client, night, lambda e: e["kind"] == "model_call")
        detail = client.get(f"/events/{event['id']}").json()
        assert detail["payload"]
        assert detail["label"] == event["label"]

    def test_detail_carries_the_model_calls_of_its_invocation(self, client, night):
        event = self._first(client, night, lambda e: e["kind"] == "model_call")
        calls = client.get(f"/events/{event['id']}").json()["model_calls"]
        assert calls
        for call in calls:
            assert call["model"] and call["provider"]
            assert call["total_tokens"] > 0
            assert call["estimated_cost_usd"] is not None

    def test_every_call_of_the_invocation_is_returned_not_one_guessed_at(
        self, client, night, repo
    ):
        event = self._first(client, night, lambda e: e["kind"] == "model_call")
        expected = repo.model_calls_for_invocation(event["agent_invocation_id"])
        returned = client.get(f"/events/{event['id']}").json()["model_calls"]
        assert [c["id"] for c in returned] == [r["id"] for r in expected]

    def test_an_event_with_no_invocation_reports_no_calls(self, client, night):
        event = self._first(client, night, lambda e: e["agent_invocation_id"] is None)
        assert client.get(f"/events/{event['id']}").json()["model_calls"] == []

    def test_an_unknown_event_is_refused(self, client, night):
        assert client.get("/events/99999999").status_code == 404

    def test_no_prompt_or_completion_text_is_served(self, client, night):
        """`model_call_payloads` holds what was said.

        The constitution names an export path that includes it as a Privacy
        Airlock violation, so the detail response has no field it could travel
        in — counts and costs are accounting, the words are not.
        """
        event = self._first(client, night, lambda e: e["kind"] == "model_call")
        detail = client.get(f"/events/{event['id']}").json()
        forbidden = {"prompt", "completion", "prompt_path", "completion_path",
                     "prompt_text", "completion_text"}
        assert not forbidden & set(detail)
        for call in detail["model_calls"]:
            assert not forbidden & set(call)


class TestTheTimelineNeverWrites:
    def test_reading_a_night_changes_nothing(self, client, night, repo):
        def counts() -> dict[str, int]:
            return {
                table: repo.connection.execute(
                    f"SELECT COUNT(*) n FROM {table}"  # noqa: S608 - fixed names
                ).fetchone()["n"]
                for table in ("events", "runs", "model_calls", "agent_invocations",
                              "entries", "failures")
            }

        before = counts()
        client.get("/runs")
        body = client.get(f"/runs/{night.run_id}/timeline").json()
        client.get(f"/events/{body['events'][0]['id']}")
        assert counts() == before

    def test_the_routes_offer_no_write_verb(self, client):
        for path in ("/runs", "/events/1"):
            assert client.post(path, json={}).status_code == 405
