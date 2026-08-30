"""Timeline reads: ordering, extent, lanes, framing, buckets and spend.

Asserted against a real generated night rather than fixtures, because every one
of these requirements exists because the generated night broke a naive
assumption.
"""

from __future__ import annotations

import pytest

from secondshift.db.connection import now_ms
from secondshift.db.repository import Repository
from secondshift_seed.night import generate_night

SEED = 42


@pytest.fixture
def night(repo):
    return generate_night(repo, seed=SEED)


class TestOrderingAndPaging:
    def test_the_integer_key_is_not_monotonic_in_time(self, repo, night):
        """The premise. If this ever stops being true the paging is over-built."""
        rows = repo.connection.execute(
            "SELECT id, ts_ms FROM events WHERE run_id = ? ORDER BY id", (night.run_id,)
        ).fetchall()
        inversions = sum(1 for a, b in zip(rows, rows[1:]) if b["ts_ms"] < a["ts_ms"])
        assert inversions > 0

    def test_timeline_is_ordered_by_time(self, repo, night):
        rows = repo.timeline(night.run_id)
        assert all(a["ts_ms"] <= b["ts_ms"] for a, b in zip(rows, rows[1:]))

    def test_paging_returns_every_event_exactly_once(self, repo, night):
        seen: list[int] = []
        cursor = None
        while True:
            page = repo.timeline(night.run_id, limit=100, after=cursor)
            if not page:
                break
            seen.extend(r["id"] for r in page)
            cursor = (page[-1]["ts_ms"], page[-1]["id"])
        assert len(seen) == len(set(seen))
        assert set(seen) == {r["id"] for r in repo.timeline(night.run_id)}

    def test_paging_does_not_stall_on_shared_timestamps(self, repo, night):
        shared = repo.connection.execute(
            "SELECT ts_ms FROM events WHERE run_id = ? GROUP BY ts_ms HAVING COUNT(*) > 1",
            (night.run_id,),
        ).fetchall()
        assert shared, "the night must contain a collision for this to be meaningful"
        total = len(repo.timeline(night.run_id))
        pages, cursor = 0, None
        # Bounded above the real count so a stall fails rather than hangs, and a
        # cap that is merely too low cannot masquerade as one.
        while pages < total + 10:
            page = repo.timeline(night.run_id, limit=1, after=cursor)
            if not page:
                break
            cursor = (page[0]["ts_ms"], page[0]["id"])
            pages += 1
        assert pages == len(repo.timeline(night.run_id))


class TestWindow:
    def test_a_window_excludes_events_outside_it(self, repo, night):
        lo, hi = repo.timeline_extent(night.run_id)
        mid = lo + (hi - lo) // 2
        window = repo.timeline(night.run_id, from_ms=mid, to_ms=hi)
        assert window
        assert all(r["ts_ms"] <= hi for r in window)
        assert len(window) < len(repo.timeline(night.run_id))

    def test_a_bar_running_into_the_window_is_included(self, repo, run_id):
        """A forty-second crawl that began before the window is inside it."""
        start = now_ms()
        repo.insert_event(
            lane="researcher", kind="extract", label="a long crawl",
            run_id=run_id, ts_ms=start, duration_ms=40_000,
        )
        rows = repo.timeline(run_id, from_ms=start + 20_000, to_ms=start + 60_000)
        assert [r["label"] for r in rows] == ["a long crawl"]


class TestExtent:
    def test_the_extent_covers_bars_past_the_last_instant(self, repo, night):
        lo, hi = repo.timeline_extent(night.run_id)
        last_instant = repo.connection.execute(
            "SELECT MAX(ts_ms) m FROM events WHERE run_id = ?", (night.run_id,)
        ).fetchone()["m"]
        assert hi > last_instant

    def test_an_empty_run_has_no_extent(self, repo, run_id):
        assert repo.timeline_extent(run_id) is None


class TestLanes:
    def test_the_roster_is_the_whole_run(self, repo, night):
        roster = repo.lane_roster(night.run_id)
        assert len(roster) > 1
        assert roster == sorted(roster)

    def test_the_roster_does_not_shrink_with_the_window(self, repo, night):
        lo, hi = repo.timeline_extent(night.run_id)
        narrow = repo.timeline(night.run_id, from_ms=lo, to_ms=lo + 60_000)
        assert set(r["lane"] for r in narrow) < set(repo.lane_roster(night.run_id))

    def test_an_invocation_reports_its_role(self, repo, night):
        tree = repo.invocation_tree(night.run_id)
        assert tree
        assert all(r["role"] for r in tree)
        assert len({r["role"] for r in tree}) > 1


class TestFraming:
    def test_run_detail_carries_the_capture_offset(self, repo, night):
        detail = repo.run_detail(night.run_id)
        assert detail["captured_tz"]
        assert isinstance(detail["tz_offset_min"], int)

    def test_run_detail_is_none_for_an_unknown_run(self, repo):
        assert repo.run_detail("01MNOTAREALRUNIDENTIFIER00") is None

    def test_the_evening_captures_are_reachable(self, repo, night):
        captures = repo.captures_before_run(night.run_id)
        assert captures
        started = repo.run_detail(night.run_id)["started_at_ms"]
        assert all(c["created_at_ms"] <= started for c in captures)

    def test_stages_include_one_still_running(self, repo, night):
        stages = repo.run_stages(night.run_id)
        assert stages
        assert any(s["status"] == "running" for s in stages)
        assert [s["seq"] for s in stages] == sorted(s["seq"] for s in stages)


class TestBuckets:
    def test_an_error_survives_being_zoomed_out(self, repo, run_id):
        base = now_ms()
        for i in range(40):
            repo.insert_event(
                lane="researcher", kind="search", label=f"routine {i}",
                run_id=run_id, ts_ms=base + i, severity="info",
            )
        repo.insert_event(
            lane="researcher", kind="error", label="the one that matters",
            run_id=run_id, ts_ms=base + 5, severity="error",
        )
        buckets = repo.timeline_buckets(run_id, bucket_ms=60_000)
        assert len(buckets) == 1
        assert buckets[0]["count"] == 41
        assert buckets[0]["severity_rank"] == 3

    def test_buckets_are_per_lane(self, repo, night):
        buckets = repo.timeline_buckets(night.run_id, bucket_ms=600_000)
        assert len({b["lane"] for b in buckets}) > 1
        assert sum(b["count"] for b in buckets) == len(repo.timeline(night.run_id))


class TestSpend:
    def test_spend_is_summed_from_calls_not_from_the_views(self, repo, night):
        spend = repo.run_spend(night.run_id)
        assert spend["calls"] > 0
        assert spend["total_tokens"] > 0
        # The rollup view excludes synthetic rows, which is why it is not used.
        assert repo.connection.execute(
            "SELECT COUNT(*) n FROM run_cost WHERE run_id = ?", (night.run_id,)
        ).fetchone()["n"] == 0

    def test_a_generated_night_reports_itself_as_generated(self, repo, night):
        assert repo.run_spend(night.run_id)["any_synthetic"] == 1

    def test_an_empty_run_reports_zero_rather_than_null(self, repo, run_id):
        spend = repo.run_spend(run_id)
        assert spend["spend_usd"] == 0 and spend["calls"] == 0
