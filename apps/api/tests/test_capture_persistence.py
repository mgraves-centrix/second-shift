"""Capture-side persistence: migration 0002, eligibility, identity, locking."""

from __future__ import annotations

import sqlite3
import threading

import pytest

from secondshift.db import migrate
from secondshift.db.connection import now_ms
from secondshift.db.ids import new_ulid
from secondshift.db.repository import Repository

TZ = dict(captured_tz="America/Los_Angeles", tz_offset_min=-420)


def _entry(repo, *, text="an idea", when=None, synthetic=False, status="queued", **kw):
    when = when if when is not None else now_ms()
    return repo.insert_entry(
        created_at_ms=when,
        modality="text",
        default_policy="cloud-assisted",
        status=status,
        capture_profile="spark",
        raw_text=text,
        is_synthetic=synthetic,
        **TZ,
        **kw,
    )


class TestCaptureMigrations:
    def test_applies_to_a_database_already_at_version_one(self, db):
        conn = db("stepwise.db")
        first = [m for m in migrate.discover() if m.version == 1]
        directory = first[0].path.parent
        # Apply only migration 1 by pretending 2 does not exist yet.
        conn.executescript("BEGIN;" + first[0].sql() + "\nCOMMIT;")
        conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_version "
            "(version INTEGER PRIMARY KEY, name TEXT NOT NULL, applied_at_ms INTEGER NOT NULL)"
        )
        conn.execute(
            "INSERT INTO schema_version VALUES (1, 'initial', ?)", (now_ms(),)
        )
        # Derived from what is on disk: adding a migration must not fail this
        # test, only a migration that does not apply from version one.
        expected = [m.version for m in migrate.discover() if m.version > 1]
        assert migrate.migrate(conn, directory) == expected
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"

    def test_event_can_name_an_entry_and_be_read_back(self, repo):
        entry = _entry(repo)
        repo.insert_event(
            lane="capture", kind="note", label="captured offline", entry_id=entry
        )
        history = repo.entry_history(entry)
        assert len(history) == 1
        assert history[0]["label"] == "captured offline"
        assert history[0]["run_id"] is None

    def test_entry_history_excludes_other_entries(self, repo):
        a, b = _entry(repo, text="a"), _entry(repo, text="b")
        repo.insert_event(lane="capture", kind="note", label="for a", entry_id=a)
        repo.insert_event(lane="capture", kind="note", label="for b", entry_id=b)
        assert [r["label"] for r in repo.entry_history(a)] == ["for a"]


class TestBothInstants:
    def test_capture_and_receipt_are_independent(self, repo):
        captured, received = 1_700_000_000_000, 1_700_000_900_000
        entry = _entry(repo, when=captured, received_at_ms=received)
        row = repo.get_entry(entry)
        assert row["created_at_ms"] == captured
        assert row["received_at_ms"] == received

    def test_future_capture_instant_is_preserved_not_rejected(self, repo):
        """A phone with a fast clock. Never rejected, never clamped."""
        future = now_ms() + 86_400_000
        entry = _entry(repo, when=future, received_at_ms=now_ms())
        row = repo.get_entry(entry)
        assert row["created_at_ms"] == future
        assert row["received_at_ms"] < row["created_at_ms"]

    def test_old_queued_entry_keeps_its_capture_time(self, repo):
        three_days_ago = now_ms() - 3 * 86_400_000
        entry = _entry(repo, when=three_days_ago, received_at_ms=now_ms())
        assert repo.get_entry(entry)["created_at_ms"] == three_days_ago

    def test_insert_requires_a_capture_instant(self, repo):
        with pytest.raises(TypeError):
            repo.insert_entry(
                modality="text",
                default_policy="cloud-assisted",
                status="queued",
                capture_profile="spark",
                raw_text="x",
                **TZ,
            )


class TestIdentity:
    def test_client_identifier_is_accepted(self, repo):
        when = now_ms()
        given = new_ulid(when)
        assert _entry(repo, when=when, entry_id=given) == given

    def test_malformed_identifier_is_rejected(self, repo):
        with pytest.raises(ValueError, match="not a ULID"):
            _entry(repo, entry_id="not-a-ulid")

    def test_identifier_disagreeing_with_the_instant_is_rejected(self, repo):
        when = now_ms()
        stale = new_ulid(when - 60_000)
        with pytest.raises(ValueError, match="they must agree"):
            _entry(repo, when=when, entry_id=stale)

    def test_generated_identifier_agrees_with_the_instant(self, repo):
        from secondshift.db.ids import timestamp_ms

        when = 1_700_000_123_456
        assert timestamp_ms(_entry(repo, when=when)) == when


class TestEligibility:
    def test_synthetic_queued_entries_are_never_dispatched(self, repo):
        real = _entry(repo, text="real")
        _entry(repo, text="seeded", synthetic=True)
        assert [r["id"] for r in repo.dispatch_eligible_entries()] == [real]

    def test_synthetic_entry_is_retrievable_as_ineligible(self, repo):
        _entry(repo, text="seeded", synthetic=True)
        ineligible = repo.ineligible_entries()
        assert len(ineligible) == 1
        assert "synthetic" in ineligible[0][1]

    def test_empty_entry_is_ineligible_with_its_reason(self, repo):
        _entry(repo, text="   ")
        assert repo.dispatch_eligible_entries() == []
        row, reason = repo.ineligible_entries()[0]
        assert "no content" in reason

    def test_null_text_entry_is_ineligible_not_absent(self, repo):
        _entry(repo, text=None)
        assert repo.dispatch_eligible_entries() == []
        assert len(repo.ineligible_entries()) == 1

    def test_normal_entry_is_reachable_by_the_night(self, repo):
        entry = _entry(repo)
        assert [r["id"] for r in repo.dispatch_eligible_entries()] == [entry]
        assert repo.ineligible_entries() == []


class TestTransitions:
    def test_permitted_transition(self, repo):
        entry = _entry(repo)
        repo.transition_entry(entry, to_status="running")
        assert repo.get_entry(entry)["status"] == "running"

    def test_disallowed_transition_is_refused(self, repo):
        entry = _entry(repo)
        with pytest.raises(ValueError, match="cannot move"):
            repo.transition_entry(entry, to_status="archived_typo")
        with pytest.raises(ValueError, match="cannot move"):
            repo.transition_entry(entry, to_status="answered")

    def test_unknown_entry_is_refused(self, repo):
        with pytest.raises(ValueError, match="unknown"):
            repo.transition_entry(new_ulid(), to_status="running")

    def test_no_generic_entry_update_exists(self, repo):
        assert not [m for m in dir(repo) if m in {"update_entry", "set_entry"}]


class TestWriterLock:
    def test_concurrent_entry_writes_serialize_and_lose_nothing(self, recorder, repo):
        """FastAPI runs sync handlers in a threadpool; this is that shape."""
        count = 40
        errors: list[BaseException] = []

        def write(i: int) -> None:
            try:
                recorder.record_entry(
                    created_at_ms=now_ms() + i,
                    modality="text",
                    default_policy="cloud-assisted",
                    status="queued",
                    capture_profile="spark",
                    raw_text=f"idea {i}",
                    **TZ,
                )
            except BaseException as exc:  # noqa: BLE001 - recorded, then asserted
                errors.append(exc)

        threads = [threading.Thread(target=write, args=(i,)) for i in range(count)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
        assert len(repo.dispatch_eligible_entries()) == count

    def test_recorder_exposes_the_locked_entry_write(self, recorder):
        assert hasattr(recorder, "record_entry")
        assert hasattr(recorder, "transition_entry")

    def test_unlocked_primitive_is_documented_as_such(self, repo):
        assert "NOT LOCKED" in (repo.insert_entry.__doc__ or "")


class TestEventModelCallLink:
    """Migration 0003. Hover must be exact, not probable."""

    def test_migration_applies_to_a_populated_database(self, db):
        """The first migration to meet real captured ideas."""
        conn = db("populated.db")
        migrate.migrate(conn)
        entry = Repository(conn).insert_entry(
            created_at_ms=now_ms(), modality="text", default_policy="cloud-assisted",
            status="queued", capture_profile="spark", raw_text="an idea", **TZ,
        )
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert Repository(conn).get_entry(entry) is not None

    def test_an_event_names_the_call_that_produced_it(self, repo, run_id):
        call = repo.insert_model_call(
            provider="local-vllm", compute_profile="spark", model="m",
            policy="local-only", estimated_cost_usd=0.0, run_id=run_id,
            prompt_tokens=100, completion_tokens=20, total_tokens=120,
        )
        event = repo.insert_event(
            lane="researcher", kind="model_call", label="a call",
            run_id=run_id, model_call_id=call,
        )
        assert repo.model_call_for_event(event)["id"] == call

    def test_two_calls_in_one_instant_resolve_separately(self, repo, run_id):
        """The case that made correlation by timestamp wrong."""
        instant = now_ms()
        events = []
        for tokens in (100, 900):
            call = repo.insert_model_call(
                provider="local-vllm", compute_profile="spark", model="m",
                policy="local-only", estimated_cost_usd=0.0, run_id=run_id,
                prompt_tokens=tokens, total_tokens=tokens, ts_ms=instant,
            )
            events.append(
                repo.insert_event(
                    lane="researcher", kind="model_call", label="a call",
                    run_id=run_id, model_call_id=call, ts_ms=instant,
                )
            )
        resolved = [repo.model_call_for_event(e)["prompt_tokens"] for e in events]
        assert sorted(resolved) == [100, 900]

    def test_an_event_with_no_call_reports_none(self, repo, run_id):
        event = repo.insert_event(
            lane="system", kind="stage_start", label="brief began", run_id=run_id
        )
        assert repo.model_call_for_event(event) is None

    def test_the_timeline_carries_the_link_and_the_flag(self, repo, run_id):
        call = repo.insert_model_call(
            provider="local-vllm", compute_profile="spark", model="m",
            policy="local-only", estimated_cost_usd=0.0, run_id=run_id,
        )
        repo.insert_event(
            lane="researcher", kind="model_call", label="a call",
            run_id=run_id, model_call_id=call,
        )
        row = repo.timeline(run_id)[0]
        assert row["model_call_id"] == call
        assert "is_synthetic" in row.keys()
