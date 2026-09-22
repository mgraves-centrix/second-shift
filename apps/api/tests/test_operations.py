"""Taking a copy of the only machine that has the data, and putting it back.

The first class here is the reason the rest exists. Everything else checks that
the tooling refuses what it should; that one checks that the mechanism underneath
it is the right mechanism, because the obvious alternative is wrong in a way
that looks like success.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path

import pytest

from secondshift import config
from secondshift.db.connection import connect, now_ms
from secondshift.ops import create_backup, restore_backup, run_checks, verify_backup
from secondshift.ops.doctor import night_in_flight
from secondshift.ops.backup import (
    DATABASE,
    MANIFEST,
    BackupRefused,
    Manifest,
)


def _backup(db_path, artifacts_root, destination):
    """A backup for a test, which is always onto the same disk.

    `tmp_path` is one directory on one filesystem, so every fixture here is the
    local-rehearsal case that `--same-device-ok` exists for. The guard itself is
    tested in `TestABackupWillNotLandOnTheDiskItProtects`, which is the only
    place that should be calling `create_backup` without it.
    """
    return create_backup(
        db_path=db_path,
        artifacts_root=artifacts_root,
        destination=destination,
        same_device_ok=True,
    )


@pytest.fixture
def other_device(tmp_path):
    """A directory on a different storage device from `tmp_path`.

    A real second filesystem rather than a patched `st_dev`: the thing under
    test is a comparison of two devices, and replacing the comparison with an
    answer would test the test. `/dev/shm` is tmpfs on Linux and `/tmp` here is
    not, which is the whole requirement.
    """
    import os
    import shutil
    import tempfile

    shm = Path("/dev/shm")
    if not (shm.is_dir() and os.access(shm, os.W_OK)):
        pytest.skip("no writable second filesystem to compare against")
    if os.stat(shm).st_dev == os.stat(tmp_path).st_dev:
        pytest.skip("/dev/shm is the same device as the temporary directory")

    made = Path(tempfile.mkdtemp(dir=shm, prefix="second-shift-"))
    yield made
    shutil.rmtree(made, ignore_errors=True)


@pytest.fixture
def machine(tmp_path):
    """A data directory shaped like the one on the always-on machine."""
    data = tmp_path / "second-shift-data"
    artifacts = data / "artifacts"
    artifacts.mkdir(parents=True)
    (artifacts / "2026-08-27").mkdir()
    (artifacts / "2026-08-27" / "brief.md").write_text("# an idea\n\nand what to do about it\n")

    db = data / "second-shift.db"
    conn = connect(db)
    from secondshift.db.migrate import migrate

    migrate(conn)
    repo_entry = conn.execute(
        "INSERT INTO entries (id, created_at_ms, received_at_ms, captured_tz, "
        "tz_offset_min, modality, default_policy, status, capture_profile, raw_text) "
        "VALUES ('01M13BW0B39C6RTMM8Y4A2RFZ8', ?, ?, 'America/Los_Angeles', -420, "
        "'text', 'local-only', 'queued', 'spark', 'a tool that notices repeats')",
        (now_ms(), now_ms()),
    )
    assert repo_entry.rowcount == 1
    conn.close()
    return db, artifacts


class TestTheMechanismIsTheRightMechanism:
    """Why the database is not copied with `cp`.

    The database runs `PRAGMA journal_mode = WAL`, so committed transactions —
    including `CREATE TABLE` — live in the `-wal` file until a checkpoint moves
    them. Nothing forces a checkpoint at any particular moment.
    """

    def test_copying_the_file_alone_loses_committed_data(self, tmp_path):
        import shutil

        live = tmp_path / "live.db"
        conn = connect(live)
        conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, v TEXT)")
        conn.executemany(
            "INSERT INTO t (v) VALUES (?)", [(f"row {i}",) for i in range(500)]
        )
        assert conn.execute("SELECT count(*) AS n FROM t").fetchone()["n"] == 500

        shutil.copy(live, tmp_path / "naive.db")
        naive = sqlite3.connect(tmp_path / "naive.db")
        try:
            with pytest.raises(sqlite3.OperationalError, match="no such table"):
                naive.execute("SELECT count(*) FROM t")
        finally:
            naive.close()
            conn.close()

    def test_the_online_backup_gets_every_committed_row_under_a_writer(self, tmp_path):
        """And none of the uncommitted one, which is the whole point of it."""
        live = tmp_path / "live.db"
        conn = connect(live)
        conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, v TEXT)")
        conn.executemany(
            "INSERT INTO t (v) VALUES (?)", [(f"row {i}",) for i in range(500)]
        )

        writer = connect(live)
        writer.execute("BEGIN")
        writer.execute("INSERT INTO t (v) VALUES ('uncommitted')")

        copied = sqlite3.connect(tmp_path / "online.db")
        conn.backup(copied)
        writer.execute("ROLLBACK")

        assert copied.execute("SELECT count(*) FROM t").fetchone()[0] == 500
        assert copied.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        copied.close()
        writer.close()
        conn.close()


class TestWhatABackupRecords:
    def test_the_manifest_counts_every_table(self, machine, tmp_path):
        db, artifacts = machine
        manifest = _backup(db, artifacts, tmp_path / "b")

        assert manifest.tables["entries"] == 1
        assert manifest.tables["runs"] == 0
        assert manifest.schema_version == 3

    def test_it_counts_the_artifacts(self, machine, tmp_path):
        db, artifacts = machine
        manifest = _backup(db, artifacts, tmp_path / "b")

        assert manifest.artifact_files == 1
        assert manifest.artifact_bytes == (artifacts / "2026-08-27" / "brief.md").stat().st_size

    def test_it_digests_every_member(self, machine, tmp_path):
        db, artifacts = machine
        manifest = _backup(db, artifacts, tmp_path / "b")

        assert {m.path for m in manifest.members} == {
            DATABASE,
            "artifacts/2026-08-27/brief.md",
        }
        assert all(len(m.sha256) == 64 for m in manifest.members)

    def test_it_names_the_brain_as_excluded_with_a_reason(self, machine, tmp_path):
        """Silence would let an operator conclude the brain was included."""
        db, artifacts = machine
        manifest = _backup(db, artifacts, tmp_path / "b")

        assert "brain" in manifest.excluded
        assert "mirror" in manifest.excluded["brain"]

    def test_a_machine_that_has_never_run_a_night_still_backs_up(self, machine, tmp_path):
        """Refusing over a missing artifacts tree refuses the case that matters most."""
        db, _ = machine
        manifest = _backup(db, tmp_path / "never-existed", tmp_path / "b")

        assert manifest.artifact_files == 0
        assert manifest.tables["entries"] == 1


class TestARefusal:
    def test_a_destination_that_already_holds_a_backup(self, machine, tmp_path):
        db, artifacts = machine
        _backup(db, artifacts, tmp_path / "b")

        with pytest.raises(BackupRefused, match="already holds a backup"):
            _backup(db, artifacts, tmp_path / "b")

    def test_a_database_that_is_not_there(self, tmp_path):
        with pytest.raises(BackupRefused, match="no database at"):
            _backup(tmp_path / "absent.db", tmp_path, tmp_path / "b")

    def test_restoring_onto_an_occupied_path(self, machine, tmp_path):
        db, artifacts = machine
        _backup(db, artifacts, tmp_path / "b")

        with pytest.raises(BackupRefused, match="already exists"):
            restore_backup(source=tmp_path / "b", db_path=db, artifacts_root=artifacts)

    def test_the_refusal_says_what_is_already_there(self, machine, tmp_path):
        """A refusal that does not say what it is protecting is an obstruction."""
        db, artifacts = machine
        _backup(db, artifacts, tmp_path / "b")

        with pytest.raises(BackupRefused) as raised:
            restore_backup(source=tmp_path / "b", db_path=db, artifacts_root=artifacts)

        # Four, not one: the entry, and the three rows `migrate` wrote to
        # `schema_version`. A count that excluded the schema's own bookkeeping
        # would describe a different database from the one being protected.
        assert "17 tables and 4 rows" in str(raised.value)

    def test_the_overwrite_proceeds(self, machine, tmp_path):
        db, artifacts = machine
        _backup(db, artifacts, tmp_path / "b")

        manifest = restore_backup(
            source=tmp_path / "b",
            db_path=db,
            artifacts_root=artifacts,
            overwrite=True,
        )

        assert manifest.tables["entries"] == 1


class TestABackupWillNotLandOnTheDiskItProtects:
    """The failure the nightly schedule creates, rather than one the mechanism
    had.

    The destination is a mount point on a machine where the share might not be
    mounted, and an unmounted mount point is an ordinary empty directory on the
    local disk. Every backup then succeeds, the staleness check reports them
    fresh, and all of them sit on the one device whose failure this capability
    exists for.
    """

    def test_the_same_disk_is_refused(self, machine, tmp_path):
        db, artifacts = machine

        with pytest.raises(BackupRefused, match="same device"):
            create_backup(
                db_path=db, artifacts_root=artifacts, destination=tmp_path / "b"
            )

    def test_the_refusal_names_the_way_out(self, machine, tmp_path):
        """A rehearsal is a real use, and an obstruction that does not say how
        to proceed is one somebody routes around."""
        db, artifacts = machine

        with pytest.raises(BackupRefused) as raised:
            create_backup(
                db_path=db, artifacts_root=artifacts, destination=tmp_path / "b"
            )

        assert "--same-device-ok" in str(raised.value)
        assert "not mounted" in str(raised.value)

    def test_a_deliberate_rehearsal_proceeds(self, machine, tmp_path):
        db, artifacts = machine

        manifest = create_backup(
            db_path=db,
            artifacts_root=artifacts,
            destination=tmp_path / "b",
            same_device_ok=True,
        )

        assert manifest.tables["entries"] == 1

    def test_another_device_needs_no_flag(self, machine, other_device):
        """What the nightly unit does, against a real second filesystem."""
        db, artifacts = machine

        manifest = create_backup(
            db_path=db, artifacts_root=artifacts, destination=other_device / "b"
        )

        assert manifest.tables["entries"] == 1

    def test_a_destination_that_does_not_exist_yet_is_judged_by_its_parent(
        self, machine, other_device
    ):
        """A backup's destination is a directory that does not exist yet, so the
        device that matters is the one it will be created on."""
        db, artifacts = machine

        manifest = create_backup(
            db_path=db,
            artifacts_root=artifacts,
            destination=other_device / "nested" / "deeper" / "b",
        )

        assert manifest.tables["entries"] == 1


class TestVerifying:
    @pytest.fixture
    def backup(self, machine, tmp_path):
        db, artifacts = machine
        _backup(db, artifacts, tmp_path / "b")
        return tmp_path / "b"

    def test_an_intact_backup_has_no_problems(self, backup):
        assert verify_backup(backup) == []

    def test_a_changed_member_is_named(self, backup):
        target = backup / "artifacts" / "2026-08-27" / "brief.md"
        target.write_text(target.read_text() + "tampered")

        assert any("brief.md" in p for p in verify_backup(backup))

    def test_a_member_changed_without_changing_its_size_is_caught(self, backup):
        """The digest, not the byte count. A same-length edit is the one a size
        check would wave through, and it is also the one an edit makes."""
        target = backup / "artifacts" / "2026-08-27" / "brief.md"
        original = target.read_bytes()
        target.write_bytes(b"X" * len(original))

        assert any("recorded digest" in p for p in verify_backup(backup))

    def test_a_missing_member_is_named(self, backup):
        (backup / "artifacts" / "2026-08-27" / "brief.md").unlink()

        assert any("recorded and missing" in p for p in verify_backup(backup))

    def test_an_unrecorded_file_is_named(self, backup):
        """Something added to a backup is not the backup that was taken."""
        (backup / "extra.txt").write_text("where did this come from")

        assert any("not in its manifest" in p for p in verify_backup(backup))

    def test_a_manifest_that_disagrees_about_counts_is_caught(self, backup):
        manifest = json.loads((backup / MANIFEST).read_text())
        manifest["tables"]["entries"] = 99
        (backup / MANIFEST).write_text(json.dumps(manifest))

        assert any("entries holds 1 rows, recorded as 99" in p for p in verify_backup(backup))

    def test_a_manifest_that_disagrees_about_the_schema_is_caught(self, backup):
        manifest = json.loads((backup / MANIFEST).read_text())
        manifest["schema_version"] = 99
        (backup / MANIFEST).write_text(json.dumps(manifest))

        assert any("recorded as 99" in p for p in verify_backup(backup))

    def test_a_directory_with_no_manifest_proves_nothing(self, tmp_path):
        (tmp_path / "not-a-backup").mkdir()

        assert verify_backup(tmp_path / "not-a-backup") == [
            f"{tmp_path / 'not-a-backup'} holds no manifest, so nothing about it can be checked"
        ]

    def test_a_damaged_backup_is_not_restored(self, backup, tmp_path):
        """One problem stays one problem. Restoring damage over a working
        database is how a bad day becomes two."""
        (backup / DATABASE).write_bytes(b"not a database")

        with pytest.raises(BackupRefused, match="does not match its manifest"):
            restore_backup(
                source=backup,
                db_path=tmp_path / "elsewhere.db",
                artifacts_root=tmp_path / "elsewhere",
            )


class TestRestoring:
    def test_the_restored_database_is_the_one_that_was_taken(self, machine, tmp_path):
        """Dumped and compared, not counted. Counts agreeing is what the
        manifest already checks; this is whether the bytes came back."""
        db, artifacts = machine
        _backup(db, artifacts, tmp_path / "b")

        restore_backup(
            source=tmp_path / "b",
            db_path=tmp_path / "restored" / "second-shift.db",
            artifacts_root=tmp_path / "restored" / "artifacts",
        )

        original = sqlite3.connect(db)
        restored = sqlite3.connect(tmp_path / "restored" / "second-shift.db")
        try:
            assert "\n".join(restored.iterdump()) == "\n".join(original.iterdump())
        finally:
            original.close()
            restored.close()

    def test_the_artifacts_come_back(self, machine, tmp_path):
        db, artifacts = machine
        _backup(db, artifacts, tmp_path / "b")

        restore_backup(
            source=tmp_path / "b",
            db_path=tmp_path / "restored" / "second-shift.db",
            artifacts_root=tmp_path / "restored" / "artifacts",
        )

        landed = tmp_path / "restored" / "artifacts" / "2026-08-27" / "brief.md"
        assert landed.read_text() == (artifacts / "2026-08-27" / "brief.md").read_text()

    def test_a_stale_write_ahead_log_is_removed(self, machine, tmp_path):
        """A `-wal` beside a database it does not belong to is read as that
        database's committed tail, which is how a restore silently un-restores."""
        db, artifacts = machine
        _backup(db, artifacts, tmp_path / "b")

        target = tmp_path / "restored" / "second-shift.db"
        target.parent.mkdir()
        Path(f"{target}-wal").write_bytes(b"somebody else's tail")

        restore_backup(
            source=tmp_path / "b",
            db_path=target,
            artifacts_root=tmp_path / "restored" / "artifacts",
        )

        assert not Path(f"{target}-wal").exists()


class TestWhetherANightIsInFlight:
    """The precondition for restarting anything on that machine.

    `docker rm -f` on the reasoner during a night costs that night its morning,
    and the night is the product. The lock is held by a real second process in
    every test here: the thing under test is a `flock`, and a simulated one
    would test the simulation.
    """

    @contextmanager
    def _a_night_holding_the_lock(self, db_path: Path):
        import subprocess
        import sys

        held = subprocess.Popen(
            [
                sys.executable,
                "-c",
                "import fcntl, sys, time\n"
                f"h = open({str(db_path) + '.night.lock'!r}, 'a')\n"
                "fcntl.flock(h, fcntl.LOCK_EX)\n"
                "print('held', flush=True)\n"
                "time.sleep(60)\n",
            ],
            stdout=subprocess.PIPE,
            text=True,
        )
        assert held.stdout.readline().strip() == "held"
        try:
            yield held
        finally:
            held.kill()
            held.wait()
            held.stdout.close()

    def test_a_running_night_is_seen(self, machine):
        db, _ = machine

        with self._a_night_holding_the_lock(db):
            assert night_in_flight(db) is True

    def test_an_idle_machine_is_seen(self, machine):
        db, _ = machine
        Path(f"{db}.night.lock").touch()

        assert night_in_flight(db) is False

    def test_a_machine_that_has_never_run_a_night_is_idle(self, machine):
        """Not broken. The judge container is exactly this."""
        db, _ = machine

        assert not Path(f"{db}.night.lock").exists()
        assert night_in_flight(db) is False

    def test_a_night_that_died_holding_the_lock_does_not_hold_it(self, machine):
        """The reason this reads a lock and not an open `runs` row.

        A killed night leaves a run open — that is what `recover_interrupted`
        exists for — and a restart gated on that evidence would refuse forever.
        The kernel releases the lock when the process exits however it exits.
        """
        db, _ = machine

        with self._a_night_holding_the_lock(db) as held:
            held.kill()
            held.wait()

        assert night_in_flight(db) is False

    def test_the_command_exits_three_so_it_can_gate_a_restart(self, machine):
        from secondshift.ops.__main__ import NIGHT_IN_FLIGHT, main

        db, _ = machine
        with self._a_night_holding_the_lock(db):
            assert main(["--db", str(db), "night-status"]) == NIGHT_IN_FLIGHT

    def test_the_exit_code_is_the_night_s_own(self):
        """Two commands must not answer the same state with different codes.

        Asserted rather than imported: `night.__main__` drags in FastAPI, and
        `ops` runs on a bare python3 before the venv exists. The first draft did
        import it, and the stdlib-only test caught it — which is a deploy that
        did not break rather than a test that did.
        """
        from secondshift.night.__main__ import EXIT_ALREADY_RUNNING
        from secondshift.ops.__main__ import NIGHT_IN_FLIGHT

        assert NIGHT_IN_FLIGHT == EXIT_ALREADY_RUNNING

    def test_the_command_exits_zero_when_idle(self, machine):
        from secondshift.ops.__main__ import main

        db, _ = machine

        assert main(["--db", str(db), "night-status"]) == 0


class TestDoctor:
    @pytest.fixture
    def well(self, machine, other_device):
        """A machine with nothing wrong with it, which includes its backups
        being somewhere other than the disk they protect."""
        db, artifacts = machine
        _backup(db, artifacts, other_device / "backups" / "one")
        return {
            config.ENV_DB: str(db),
            config.ENV_ARTIFACTS: str(artifacts),
            config.ENV_PROFILE: "cloud",
        }, other_device / "backups"

    def test_a_well_machine_passes_every_check(self, well):
        env, backups = well

        assert [c.name for c in run_checks(env=env, backups=backups) if not c.ok] == []

    def test_a_missing_database_fails(self, well, tmp_path):
        env, backups = well
        env[config.ENV_DB] = str(tmp_path / "gone.db")

        failed = {c.name for c in run_checks(env=env, backups=backups) if not c.ok}
        assert "database" in failed

    def test_a_database_not_in_wal_fails(self, well, tmp_path):
        """Any other mode puts a reader in the way of the night's writes."""
        env, backups = well
        rollback = tmp_path / "rollback.db"
        conn = sqlite3.connect(rollback)
        conn.execute("PRAGMA journal_mode = DELETE")
        conn.execute("CREATE TABLE schema_version (version INTEGER)")
        conn.commit()
        conn.close()
        env[config.ENV_DB] = str(rollback)

        detail = next(c for c in run_checks(env=env, backups=backups) if c.name == "database")
        assert not detail.ok
        assert "journal mode is delete" in detail.detail

    def test_a_schema_behind_the_migrations_fails(self, well):
        env, backups = well
        conn = connect(env[config.ENV_DB])
        conn.execute("DELETE FROM schema_version WHERE version = (SELECT MAX(version) FROM schema_version)")
        conn.close()

        detail = next(c for c in run_checks(env=env, backups=backups) if c.name == "schema")
        assert not detail.ok
        assert "migrations on disk go to" in detail.detail

    def test_no_backup_at_all_fails(self, well, tmp_path):
        env, _ = well

        detail = next(
            c for c in run_checks(env=env, backups=tmp_path / "nowhere") if c.name == "backups"
        )
        assert not detail.ok

    def test_a_backup_that_stopped_being_taken_fails(self, well):
        """Indistinguishable from a schedule never set up, until it matters."""
        env, backups = well
        from secondshift.ops.doctor import STALE_BACKUP_MS

        detail = next(
            c
            for c in run_checks(env=env, backups=backups, now_ms=now_ms() + STALE_BACKUP_MS + 1)
            if c.name == "backups"
        )
        assert not detail.ok
        assert "days old" in detail.detail

    def test_the_reasoner_is_not_expected_on_the_cloud_profile(self, well):
        """The judge container is exactly a machine with no local reasoner."""
        env, backups = well

        detail = next(
            c for c in run_checks(env=env, backups=backups) if c.name == "local reasoner"
        )
        assert detail.ok
        assert "cloud profile" in detail.detail

    def test_an_unreachable_reasoner_fails_where_one_is_expected(self, well):
        env, backups = well
        env[config.ENV_PROFILE] = "spark"
        env[config.ENV_LOCAL_PORT] = "9"

        detail = next(
            c for c in run_checks(env=env, backups=backups) if c.name == "local reasoner"
        )
        assert not detail.ok
        assert "unreachable" in detail.detail

    def test_it_reports_every_failure_rather_than_the_first(self, tmp_path):
        """Fixing one thing and re-running, three times, is work the first run
        could have saved."""
        env = {config.ENV_DB: str(tmp_path / "gone.db"), config.ENV_PROFILE: "spark"}

        failed = [c for c in run_checks(env=env, backups=tmp_path / "nowhere") if not c.ok]
        assert len(failed) >= 3

    def test_backups_on_the_same_disk_are_reported(self, machine, tmp_path):
        """A machine already in the state `create_backup` refuses to create.

        Weeks of successful local backups is something to be told about rather
        than to discover on the day the disk goes.
        """
        db, artifacts = machine
        _backup(db, artifacts, tmp_path / "backups" / "one")
        env = {config.ENV_DB: str(db), config.ENV_PROFILE: "cloud"}

        detail = next(
            c
            for c in run_checks(env=env, backups=tmp_path / "backups")
            if c.name == "backup location"
        )
        assert not detail.ok
        assert "not mounted" in detail.detail

    def test_backups_on_another_disk_pass(self, well):
        env, backups = well

        detail = next(
            c for c in run_checks(env=env, backups=backups) if c.name == "backup location"
        )
        assert detail.ok

    def test_a_night_in_flight_is_reported_and_is_not_a_fault(self, well, machine):
        """A night running is the machine working. It is here because it bears
        on a deploy, a restart and a reboot alike."""
        env, backups = well
        db, _ = machine
        with TestWhetherANightIsInFlight()._a_night_holding_the_lock(db):
            detail = next(
                c for c in run_checks(env=env, backups=backups) if c.name == "night"
            )

        assert detail.ok
        assert "do not restart" in detail.detail

    def test_an_idle_machine_says_so(self, well):
        env, backups = well

        detail = next(c for c in run_checks(env=env, backups=backups) if c.name == "night")
        assert detail.ok
        assert "none in flight" in detail.detail

    def test_a_named_path_is_not_second_guessed(self, well):
        """The ownership check exists for the default, which follows whoever
        runs it. A path somebody typed is a path they chose."""
        env, backups = well

        detail = next(
            c for c in run_checks(env=env, backups=backups) if c.name == "data ownership"
        )
        assert detail.ok
        assert "named explicitly" in detail.detail


class TestItRunsBeforeThereIsAnEnvironment:
    """`ops` imports nothing the orchestrator installs, and that is load-bearing.

    It lets `deploy.sh` take a backup from the incoming tree with the target's
    system `python3`, before the venv exists and before anything is destroyed.
    An import of FastAPI or numpy added here would not fail a test that only
    ran it under the development venv — it would fail a deploy, on the machine,
    at the moment the deploy was about to delete something.
    """

    #: Everything `apps/api/pyproject.toml` declares as a runtime dependency,
    #: by the name it imports under.
    INSTALLED = ("fastapi", "uvicorn", "pydantic", "numpy")

    def test_no_declared_dependency_is_imported(self):
        import subprocess
        import sys

        api = str(Path(__file__).resolve().parents[1])
        script = (
            "import sys, secondshift.ops, secondshift.ops.__main__;"
            f"print(','.join(n for n in {self.INSTALLED!r} if n in sys.modules))"
        )
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            env={"PYTHONPATH": api, "PATH": "/usr/bin:/bin"},
            check=True,
        )

        assert result.stdout.strip() == ""

    def test_the_declared_dependencies_really_are_importable(self):
        """Otherwise the test above passes by them being absent."""
        for name in self.INSTALLED:
            __import__(name)


def test_the_manifest_round_trips():
    manifest = Manifest(
        taken_at_ms=1790006023488,
        schema_version=3,
        tables={"entries": 4},
        artifact_files=2,
        artifact_bytes=99,
        members=[],
    )

    assert Manifest.from_json(manifest.to_json()) == manifest
