"""The night view's read routes, over a real generated night.

Fixtures would let every one of these pass against a night that cannot exist.
The generated night is the only body of data dense enough to break the naive
version of each of these routes — inverted identifiers, shared milliseconds,
a lane with no agent behind it, work running past the last recorded instant.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from secondshift.airlock.capability import build_report
from secondshift.api import app as app_module
from secondshift.api.app import Context, create_app
from secondshift.config import (
    CUDA,
    LOCAL_REASONER,
    SPEECH_STACK,
    Capability,
    ProbeResult,
    resolve_profile,
)
from secondshift.db.connection import now_ms
from secondshift_seed.night import DEFAULT_NIGHT_OF, generate_night

SEED = 42
UNKNOWN_RUN = "01MNOTAREALRUNIDENTIFIER00"


@pytest.fixture
def night(repo):
    return generate_night(repo, seed=SEED)


@pytest.fixture
def run_events(repo, night) -> int:
    """How many events land on the run itself.

    Not `night.event_count`: that counts every row the generator wrote, and the
    evening's captures carry no run, so they never appear on its timeline.
    """
    return len(repo.timeline(night.run_id))


@pytest.fixture
def context(repo, recorder) -> Context:
    # A fixed probe rather than the real one: these routes are indifferent to
    # the profile, and shelling out to a GPU query makes them machine-dependent.
    probe = ProbeResult(
        {
            name: Capability(name, False, "absent in this test")
            for name in (CUDA, LOCAL_REASONER, SPEECH_STACK)
        }
    )
    resolved = resolve_profile(env={}, probe_result=probe)
    return Context(
        repo=repo,
        recorder=recorder,
        profile=resolved,
        report=build_report(resolved),
        is_synthetic=True,
    )


@pytest.fixture
def client(context) -> TestClient:
    return TestClient(create_app(context))


def _all_events(client, run_id, **params):
    """Walk every page of a run's timeline, returning the events in order."""
    events, cursor = [], {}
    while True:
        page = client.get(
            f"/runs/{run_id}/timeline", params={**params, **cursor}
        ).json()
        events.extend(page["events"])
        if page["next_ts_ms"] is None:
            return events
        cursor = {
            "after_ts_ms": page["next_ts_ms"],
            "after_id": page["next_id"],
        }


class TestRunList:
    def test_a_night_lists_its_run(self, client, night):
        body = client.get("/runs", params={"night_of": DEFAULT_NIGHT_OF}).json()
        assert [r["id"] for r in body] == [night.run_id]

    def test_every_summary_field_is_present(self, client, night):
        summary = client.get("/runs", params={"night_of": DEFAULT_NIGHT_OF}).json()[0]
        assert set(summary) == {
            "id",
            "night_of",
            "started_at_ms",
            "ended_at_ms",
            "outcome",
            "effective_policy",
            "is_synthetic",
        }
        assert summary["is_synthetic"] is True
        assert summary["effective_policy"] == night.policy

    def test_another_night_is_empty_not_an_error(self, client, night):
        response = client.get("/runs", params={"night_of": "1999-01-01"})
        assert response.status_code == 200
        assert response.json() == []

    def test_an_absent_night_is_a_request_for_recent_runs(self, client):
        # Previously a 422. The view opens before anyone has named a date, so
        # requiring one made the entry point unreachable.
        assert client.get("/runs").status_code == 200


class TestRunDetail:
    def test_every_detail_field_is_present(self, client, night):
        detail = client.get(f"/runs/{night.run_id}").json()
        assert set(detail) == {
            "id",
            "entry_id",
            "night_of",
            "started_at_ms",
            "ended_at_ms",
            "outcome",
            "furthest_stage",
            "effective_policy",
            "policy_source",
            "compute_profile",
            "is_synthetic",
            "captured_tz",
            "tz_offset_min",
            "lat",
            "lon",
            "entry_title",
            "extent_start_ms",
            "extent_end_ms",
            "lanes",
            "stages",
            "captures",
            "spend",
        }

    def test_the_framing_comes_from_the_capture(self, client, night, repo):
        detail = client.get(f"/runs/{night.run_id}").json()
        entry = repo.get_entry(night.subject_entry_id)
        assert detail["entry_id"] == night.subject_entry_id
        assert detail["captured_tz"] == entry["captured_tz"]
        assert detail["tz_offset_min"] == entry["tz_offset_min"]

    def test_the_extent_covers_work_past_the_last_instant(self, client, night, repo):
        detail = client.get(f"/runs/{night.run_id}").json()
        last_instant = repo.connection.execute(
            "SELECT MAX(ts_ms) m FROM events WHERE run_id = ?", (night.run_id,)
        ).fetchone()["m"]
        assert detail["extent_end_ms"] > last_instant
        assert detail["extent_start_ms"] <= last_instant

    def test_a_run_with_no_events_has_no_extent(self, client, run_id):
        detail = client.get(f"/runs/{run_id}").json()
        assert detail["extent_start_ms"] is None
        assert detail["extent_end_ms"] is None

    def test_stages_carry_one_still_running(self, client, night):
        stages = client.get(f"/runs/{night.run_id}").json()["stages"]
        assert [s["seq"] for s in stages] == sorted(s["seq"] for s in stages)
        running = [s for s in stages if s["status"] == "running"]
        assert running and all(s["ended_at_ms"] is None for s in running)

    def test_the_evening_captures_precede_the_run(self, client, night):
        detail = client.get(f"/runs/{night.run_id}").json()
        assert detail["captures"]
        assert all(
            c["created_at_ms"] <= detail["started_at_ms"] for c in detail["captures"]
        )
        assert all(c["policy"] for c in detail["captures"])

    def test_spend_reports_itself_as_generated(self, client, night):
        spend = client.get(f"/runs/{night.run_id}").json()["spend"]
        assert spend["calls"] == len(night.model_call_ids)
        assert spend["total_tokens"] > 0
        assert spend["cloud_tokens"] > 0
        assert spend["generated"] is True

    def test_a_run_with_no_calls_reports_zero_and_not_generated(self, client, run_id):
        spend = client.get(f"/runs/{run_id}").json()["spend"]
        assert spend == {
            "spend_usd": 0,
            "total_tokens": 0,
            "cloud_tokens": 0,
            "calls": 0,
            "generated": False,
        }

    def test_an_unknown_run_is_a_404(self, client):
        assert client.get(f"/runs/{UNKNOWN_RUN}").status_code == 404


class TestLanes:
    def test_a_lane_with_no_invocations_still_appears(self, client, night):
        lanes = client.get(f"/runs/{night.run_id}").json()["lanes"]
        empty = [lane for lane in lanes if lane["invocations"] == 0]
        assert empty, "stage boundaries land on a lane no agent occupies"
        assert all(lane["role"] is None for lane in empty)

    def test_an_occupied_lane_names_its_role_and_counts(self, client, night, repo):
        detail = client.get(f"/runs/{night.run_id}").json()
        lanes = {lane["lane"]: lane for lane in detail["lanes"]}
        occupied = {lane for lane, entry in lanes.items() if entry["invocations"] > 0}
        assert len(occupied) > 1
        assert all(lanes[lane]["role"] == lane for lane in occupied)
        assert sum(lanes[lane]["invocations"] for lane in occupied) == len(
            repo.invocation_tree(night.run_id)
        )

    def test_the_roster_is_the_whole_run_not_a_window(self, client, night):
        detail = client.get(f"/runs/{night.run_id}").json()
        roster = {lane["lane"] for lane in detail["lanes"]}
        opening = client.get(
            f"/runs/{night.run_id}/timeline",
            params={
                "from_ms": detail["extent_start_ms"],
                "to_ms": detail["extent_start_ms"] + 60_000,
            },
        ).json()
        assert {e["lane"] for e in opening["events"]} < roster


class TestTimeline:
    def test_every_event_field_is_present(self, client, night):
        event = client.get(
            f"/runs/{night.run_id}/timeline", params={"limit": 1}
        ).json()["events"][0]
        assert set(event) == {
            "id",
            "ts_ms",
            "lane",
            "kind",
            "label",
            "severity",
            "duration_ms",
            "agent_invocation_id",
            "model_call_id",
            "is_synthetic",
        }

    def test_paging_returns_every_event_exactly_once(
        self, client, night, repo, run_events
    ):
        ids = [e["id"] for e in _all_events(client, night.run_id, limit=100)]
        assert len(ids) == len(set(ids))
        assert set(ids) == {r["id"] for r in repo.timeline(night.run_id)}
        assert len(ids) == run_events

    def test_paging_one_at_a_time_does_not_stall_on_a_shared_instant(
        self, client, night, repo, run_events
    ):
        shared = repo.connection.execute(
            "SELECT ts_ms FROM events WHERE run_id = ? GROUP BY ts_ms HAVING COUNT(*) > 1",
            (night.run_id,),
        ).fetchall()
        assert shared, "the night must contain a collision for this to be meaningful"
        assert len(_all_events(client, night.run_id, limit=1)) == run_events

    def test_pages_stay_ordered_by_time_across_the_boundary(self, client, night):
        events = _all_events(client, night.run_id, limit=100)
        assert all(a["ts_ms"] <= b["ts_ms"] for a, b in zip(events, events[1:]))

    def test_the_last_page_carries_no_cursor(self, client, night, run_events):
        page = client.get(
            f"/runs/{night.run_id}/timeline", params={"limit": run_events + 1}
        ).json()
        assert len(page["events"]) == run_events
        assert page["next_ts_ms"] is None and page["next_id"] is None

    def test_a_window_excludes_what_is_outside_it(
        self, client, night, repo, run_events
    ):
        lo, hi = repo.timeline_extent(night.run_id)
        mid = lo + (hi - lo) // 2
        window = _all_events(client, night.run_id, from_ms=mid, to_ms=hi, limit=500)
        assert window
        assert all(e["ts_ms"] <= hi for e in window)
        assert len(window) < run_events

    def test_half_a_cursor_is_refused(self, client, night):
        base = f"/runs/{night.run_id}/timeline"
        assert client.get(base, params={"after_ts_ms": 1}).status_code == 422
        assert client.get(base, params={"after_id": 1}).status_code == 422
        assert (
            client.get(base, params={"after_ts_ms": 1, "after_id": 1}).status_code == 200
        )

    def test_an_unknown_run_is_a_404(self, client):
        assert client.get(f"/runs/{UNKNOWN_RUN}/timeline").status_code == 404


class TestBuckets:
    def test_an_error_survives_being_zoomed_out(self, client, repo, run_id):
        base = now_ms()
        for i in range(40):
            repo.insert_event(
                lane="researcher",
                kind="search",
                label=f"routine {i}",
                run_id=run_id,
                ts_ms=base + i,
                severity="info",
            )
        repo.insert_event(
            lane="researcher",
            kind="error",
            label="the one that matters",
            run_id=run_id,
            ts_ms=base + 5,
            severity="error",
        )
        buckets = client.get(
            f"/runs/{run_id}/timeline/buckets", params={"bucket_ms": 60_000}
        ).json()
        assert len(buckets) == 1
        assert buckets[0]["count"] == 41
        assert buckets[0]["severity"] == "error"

    def test_severity_is_a_name_not_a_rank(self, client, night):
        buckets = client.get(
            f"/runs/{night.run_id}/timeline/buckets", params={"bucket_ms": 600_000}
        ).json()
        assert buckets
        assert {b["severity"] for b in buckets} <= {"debug", "info", "warn", "error"}
        assert set(buckets[0]) == {"lane", "bucket_start_ms", "count", "severity"}

    def test_buckets_account_for_every_event(self, client, night, run_events):
        buckets = client.get(
            f"/runs/{night.run_id}/timeline/buckets", params={"bucket_ms": 600_000}
        ).json()
        assert len({b["lane"] for b in buckets}) > 1
        assert sum(b["count"] for b in buckets) == run_events

    def test_an_unknown_run_is_a_404(self, client):
        assert client.get(f"/runs/{UNKNOWN_RUN}/timeline/buckets").status_code == 404


class TestEventDetail:
    def test_an_event_naming_a_call_carries_it(self, client, night, repo):
        row = repo.connection.execute(
            "SELECT id FROM events WHERE run_id = ? AND model_call_id IS NOT NULL "
            "ORDER BY ts_ms, id LIMIT 1",
            (night.run_id,),
        ).fetchone()
        detail = client.get(f"/events/{row['id']}").json()
        assert detail["event"]["id"] == row["id"]
        assert set(detail["model_call"]) == {
            "id",
            "provider",
            "model",
            "model_version",
            "effort",
            "prompt_tokens",
            "completion_tokens",
            "reasoning_tokens",
            "total_tokens",
            "latency_ms",
            "estimated_cost_usd",
            "cache_hit",
            "policy",
            "redaction_applied",
        }
        assert detail["model_call"]["id"] == detail["event"]["model_call_id"]

    def test_an_event_with_no_call_reports_none(self, client, night, repo):
        row = repo.connection.execute(
            "SELECT id FROM events WHERE run_id = ? AND model_call_id IS NULL "
            "ORDER BY ts_ms, id LIMIT 1",
            (night.run_id,),
        ).fetchone()
        detail = client.get(f"/events/{row['id']}").json()
        assert detail["model_call"] is None

    def test_stored_prompt_and_completion_text_is_not_reachable(
        self, client, night, repo
    ):
        """The airlock. The obvious next affordance is the one that breaks it.

        The generator writes no payload rows, so the case is set up here: a call
        whose raw prompt and completion were retained is exactly the call whose
        event must not carry them out.
        """
        call_id = night.model_call_ids[0]
        repo.insert_model_call_payload(
            model_call_id=call_id,
            prompt_path="payloads/prompt-under-test.txt",
            completion_path="payloads/completion-under-test.txt",
        )
        row = repo.connection.execute(
            "SELECT id FROM events WHERE model_call_id = ? ORDER BY id LIMIT 1",
            (call_id,),
        ).fetchone()
        assert row is not None, "the retained call must have an event to ask about"
        detail = client.get(f"/events/{row['id']}").json()
        assert set(detail) == {"event", "payload_json", "model_call"}
        assert "prompt-under-test" not in repr(detail)
        assert "completion-under-test" not in repr(detail)

    def test_an_unknown_event_is_a_404(self, client, night):
        assert client.get("/events/99999999").status_code == 404


class TestReadOnly:
    def test_no_read_route_writes(self, client, night, repo):
        def snapshot():
            return {
                table: repo.connection.execute(
                    f"SELECT COUNT(*) n FROM {table}"
                ).fetchone()["n"]
                for table in (
                    "runs",
                    "events",
                    "entries",
                    "model_calls",
                    "agent_invocations",
                    "run_stages",
                    "failures",
                )
            }

        before = snapshot()
        client.get("/runs", params={"night_of": DEFAULT_NIGHT_OF})
        client.get(f"/runs/{night.run_id}")
        client.get(f"/runs/{night.run_id}/timeline")
        client.get(f"/runs/{night.run_id}/timeline/buckets")
        client.get(f"/runs/{UNKNOWN_RUN}")
        assert snapshot() == before


class TestMountOrdering:
    """The static export is mounted at "/" with `html=True` and matches
    everything. A read route registered after it never runs, and the symptom is
    a 404 on a route that is plainly there in the source."""

    @pytest.fixture
    def export(self, tmp_path, monkeypatch):
        directory = tmp_path / "web-out"
        directory.mkdir()
        (directory / "index.html").write_text("<!doctype html>the shell")
        monkeypatch.setattr(app_module, "WEB_EXPORT", directory)
        return directory

    def test_a_route_registered_after_the_mount_is_unreachable(self, context, export):
        app = create_app(context)

        @app.get("/registered-too-late")
        def too_late() -> dict[str, bool]:
            return {"reached": True}

        response = TestClient(app).get("/registered-too-late")
        assert response.status_code == 404
        assert response.json() != {"reached": True}

    def test_the_night_routes_survive_the_mount(self, context, export, night):
        client = TestClient(create_app(context))
        assert client.get("/").text == "<!doctype html>the shell"
        assert client.get(f"/runs/{night.run_id}").status_code == 200
        assert client.get(f"/runs/{night.run_id}/timeline").status_code == 200
        assert client.get(f"/runs/{UNKNOWN_RUN}").status_code == 404


class TestRunsWithoutANight:
    """The first request a fresh client can make.

    The view opens before anyone has named a date, so a required `night_of`
    makes the entry point unreachable — which is how it was found: the timeline
    asked for runs, got a validation error, and rendered nothing.
    """

    def test_no_night_returns_the_most_recent_runs_first(self, client, night):
        response = client.get("/runs")
        assert response.status_code == 200

        runs = response.json()
        assert runs, "a seeded night must be discoverable without naming its date"
        starts = [r["started_at_ms"] for r in runs]
        assert starts == sorted(starts, reverse=True)

    def test_a_named_night_still_reads_forward_in_time(self, client, night):
        night = client.get("/runs").json()[0]["night_of"]

        starts = [r["started_at_ms"] for r in client.get(f"/runs?night_of={night}").json()]
        assert starts == sorted(starts)

    def test_the_limit_is_bounded(self, client, night):
        assert client.get("/runs?limit=0").status_code == 422
        assert client.get("/runs?limit=100000").status_code == 422
