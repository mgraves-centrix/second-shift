"""Persistence: migrations, append-only discipline, derived counters."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from secondshift.db import migrate
from secondshift.db.repository import APPEND_ONLY_TABLES, Repository

def _migration_dir(tmp_path: Path, count: int) -> Path:
    directory = tmp_path / "migrations"
    directory.mkdir(exist_ok=True)
    for n in range(1, count + 1):
        (directory / f"{n:04d}_step_{n}.sql").write_text(
            f"CREATE TABLE step_{n} (id INTEGER PRIMARY KEY);"
        )
    return directory


class TestMigrations:
    def test_fresh_database_applies_every_migration(self, db):
        conn = db("fresh.db")
        expected = [m.version for m in migrate.discover()]
        applied = migrate.migrate(conn)
        # Assert against what is on disk, not a hardcoded count: a new migration
        # should not fail this test, only a migration that does not apply.
        assert applied == expected
        assert migrate.current_version(conn) == max(expected)

    def test_rerun_applies_nothing(self, db):
        conn = db("rerun.db")
        migrate.migrate(conn)
        assert migrate.migrate(conn) == []

    def test_partially_migrated_applies_only_newer(self, tmp_path, db):
        directory = _migration_dir(tmp_path, 3)
        conn = db("partial.db")

        assert migrate.migrate(conn, directory) == [1, 2, 3]

        # Two more arrive later; only those are applied.
        for n in (4, 5):
            (directory / f"{n:04d}_step_{n}.sql").write_text(
                f"CREATE TABLE step_{n} (id INTEGER PRIMARY KEY);"
            )
        assert migrate.migrate(conn, directory) == [4, 5]
        assert migrate.current_version(conn) == 5

    def test_malformed_filename_is_an_error(self, tmp_path):
        directory = _migration_dir(tmp_path, 1)
        (directory / "not-a-migration.sql").write_text("SELECT 1;")
        with pytest.raises(ValueError, match="NNNN_name.sql"):
            migrate.discover(directory)

    def test_failed_migration_leaves_version_unchanged(self, tmp_path, db):
        directory = _migration_dir(tmp_path, 1)
        conn = db("broken.db")
        migrate.migrate(conn, directory)

        (directory / "0002_broken.sql").write_text("CREATE TABLE ( bad syntax;")
        with pytest.raises(Exception):
            migrate.migrate(conn, directory)
        assert migrate.current_version(conn) == 1

    def test_schema_applies_with_expected_shape(self, conn):
        tables = {
            r["name"]
            for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        assert {"entries", "runs", "agent_invocations", "model_calls", "events"} <= tables
        views = {
            r["name"]
            for r in conn.execute("SELECT name FROM sqlite_master WHERE type='view'")
        }
        assert "failure_ledger" in views


class TestAppendOnly:
    def test_no_generic_mutation_methods(self):
        public = {m for m in dir(Repository) if not m.startswith("_")}
        assert not {m for m in public if m in {"update", "delete", "execute", "raw"}}

    def test_no_update_or_delete_targets_an_append_only_table(self):
        source = Path(
            __import__("secondshift.db.repository", fromlist=["x"]).__file__
        ).read_text()
        statements = re.findall(
            r"(?:UPDATE|DELETE\s+FROM)\s+([a-z_]+)", source, re.IGNORECASE
        )
        offenders = APPEND_ONLY_TABLES.intersection(statements)
        assert not offenders, f"append-only tables mutated: {sorted(offenders)}"

    def test_recorded_model_call_has_no_mutator(self, repo, run_id):
        call = repo.insert_model_call(
            provider="local-vllm",
            compute_profile="spark",
            model="nemotron-3.5-lightning",
            policy="local-only",
            estimated_cost_usd=0.0,
            run_id=run_id,
        )
        assert repo.model_calls_for_run(run_id)[0]["id"] == call
        assert not [m for m in dir(repo) if "model_call" in m and "update" in m]

    def test_closing_an_invocation_twice_is_refused(self, repo, run_id, agent_id):
        invocation = repo.insert_agent_invocation(agent_id=agent_id, run_id=run_id)
        repo.close_invocation(invocation, outcome="success")
        with pytest.raises(ValueError, match="already closed"):
            repo.close_invocation(invocation, outcome="failed")

    def test_answering_a_decision_twice_is_refused(self, repo, run_id, conn):
        entry = conn.execute("SELECT entry_id FROM runs WHERE id = ?", (run_id,)).fetchone()
        decision = repo.insert_decision(
            entry_id=entry["entry_id"], question="Which framework?", status="open"
        )
        repo.answer_decision(decision, answer="FastAPI", status="decided")
        with pytest.raises(ValueError, match="already answered"):
            repo.answer_decision(decision, answer="Flask", status="decided")


class TestDerivedCounters:
    def test_failure_ledger_derives_recurrence(self, repo, run_id):
        for _ in range(3):
            repo.insert_failure(
                failure_type="model_timeout",
                signature="model_timeout:nemotron:read-timeout",
                message="read timed out after 60s",
                run_id=run_id,
            )
        ledger = repo.failure_ledger()
        assert len(ledger) == 1
        assert ledger[0]["recurrence_count"] == 3
        assert ledger[0]["type"] == "model_timeout"

    def test_ledger_reports_latest_resolution(self, repo, run_id):
        first = repo.insert_failure(
            failure_type="oom",
            signature="oom:vllm:kv-cache",
            message="cuda oom",
            run_id=run_id,
        )
        repo.insert_failure(
            failure_type="oom",
            signature="oom:vllm:kv-cache",
            message="cuda oom",
            run_id=run_id,
        )
        repo.resolve_failure(first, resolution="reduced max_model_len")
        ledger = repo.failure_ledger()
        assert ledger[0]["recurrence_count"] == 2
        assert ledger[0]["latest_resolution"] == "reduced max_model_len"

    def test_synthetic_failures_excluded_from_ledger(self, repo, run_id):
        repo.insert_failure(
            failure_type="network",
            signature="network:tavily:dns",
            message="dns failure",
            run_id=run_id,
            is_synthetic=True,
        )
        assert repo.failure_ledger() == []
