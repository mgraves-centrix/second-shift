"""A backup holds what every model call said, as it has always claimed to.

Every backup has printed that it "holds unredacted captured text and every
recorded model payload" since the day it was written. Until payloads were
captured that was vacuously true; once they are, a backup that copied the
database and the artifacts and not the payload directory would lose exactly the
text ADR 0007 says can never be reconstructed — on the one day a disk dies.
"""

from __future__ import annotations

import inspect
import json

import pytest

from secondshift import config
from secondshift.db.connection import connect, now_ms
from secondshift.db.migrate import migrate
from secondshift.ops import create_backup, restore_backup, verify_backup
from secondshift.ops.__main__ import main
from secondshift.ops.backup import MANIFEST, PAYLOADS


@pytest.fixture
def machine(tmp_path):
    """A data directory with a database, one artifact and one model call's text."""
    data = tmp_path / "data"
    (data / "artifacts" / "2026-10-17").mkdir(parents=True)
    (data / "artifacts" / "2026-10-17" / "brief.md").write_text("# a brief\n")
    payloads = data / "payloads"
    (payloads / "2026-10").mkdir(parents=True)
    (payloads / "2026-10" / "01CALL.prompt.json").write_text('{"messages": []}')
    (payloads / "2026-10" / "01CALL.completion.json").write_text(
        '{"text": "an answer", "finish_reason": "stop"}'
    )
    db = data / "second-shift.db"
    conn = connect(db)
    migrate(conn)
    conn.execute(
        "INSERT INTO entries (id, created_at_ms, received_at_ms, captured_tz, "
        "tz_offset_min, modality, default_policy, status, capture_profile, raw_text) "
        "VALUES ('01M13BW0B39C6RTMM8Y4A2RFZ8', ?, ?, 'UTC', 0, 'text', "
        "'local-only', 'queued', 'spark', 'an idea')",
        (now_ms(), now_ms()),
    )
    conn.close()
    return db, data / "artifacts", payloads


def _take(machine, destination):
    db, artifacts, payloads = machine
    return create_backup(
        db_path=db,
        artifacts_root=artifacts,
        payloads_root=payloads,
        destination=destination,
        same_device_ok=True,
    )


class TestABackupCarriesThePayloads:
    def test_every_payload_file_is_a_member(self, machine, tmp_path):
        manifest = _take(machine, tmp_path / "b")

        paths = {m.path for m in manifest.members}
        assert f"{PAYLOADS}/2026-10/01CALL.prompt.json" in paths
        assert f"{PAYLOADS}/2026-10/01CALL.completion.json" in paths

    def test_the_manifest_counts_them(self, machine, tmp_path):
        _, _, payloads = machine
        manifest = _take(machine, tmp_path / "b")

        files = [p for p in payloads.rglob("*") if p.is_file()]
        assert manifest.payload_files == len(files) == 2
        assert manifest.payload_bytes == sum(p.stat().st_size for p in files)

    def test_a_machine_that_has_recorded_no_call_still_backs_up(self, machine, tmp_path):
        db, artifacts, _ = machine
        manifest = create_backup(
            db_path=db,
            artifacts_root=artifacts,
            payloads_root=tmp_path / "never-existed",
            destination=tmp_path / "b",
            same_device_ok=True,
        )

        assert manifest.payload_files == 0
        assert manifest.tables["entries"] == 1

    def test_the_payload_root_cannot_be_forgotten(self):
        """No default. A caller that forgot it would write a backup that
        omits the payloads and prints that it holds them."""
        for function in (create_backup, restore_backup):
            parameter = inspect.signature(function).parameters["payloads_root"]
            assert parameter.default is inspect.Parameter.empty, function.__name__

    def test_a_changed_payload_is_caught_by_verify(self, machine, tmp_path):
        _take(machine, tmp_path / "b")
        target = tmp_path / "b" / PAYLOADS / "2026-10" / "01CALL.completion.json"
        target.write_text(target.read_text().replace("an answer", "a forgery"))

        assert any("01CALL.completion.json" in p for p in verify_backup(tmp_path / "b"))


class TestRestoringPutsThemBack:
    def test_the_payloads_come_back(self, machine, tmp_path):
        _, _, payloads = machine
        _take(machine, tmp_path / "b")
        restored = tmp_path / "restored"

        restore_backup(
            source=tmp_path / "b",
            db_path=restored / "second-shift.db",
            artifacts_root=restored / "artifacts",
            payloads_root=restored / "payloads",
        )

        landed = restored / "payloads" / "2026-10" / "01CALL.completion.json"
        assert landed.read_text() == (
            payloads / "2026-10" / "01CALL.completion.json"
        ).read_text()

    def test_a_backup_taken_before_payloads_existed_still_verifies_and_restores(
        self, machine, tmp_path
    ):
        """Five backups on the NAS predate this. A manifest without the payload
        counts is an older backup, not a damaged one."""
        db, artifacts, _ = machine
        create_backup(
            db_path=db,
            artifacts_root=artifacts,
            payloads_root=tmp_path / "none-yet",
            destination=tmp_path / "old",
            same_device_ok=True,
        )
        manifest = json.loads((tmp_path / "old" / MANIFEST).read_text())
        del manifest["payload_files"], manifest["payload_bytes"]
        (tmp_path / "old" / MANIFEST).write_text(json.dumps(manifest))

        assert verify_backup(tmp_path / "old") == []
        restored = restore_backup(
            source=tmp_path / "old",
            db_path=tmp_path / "r" / "second-shift.db",
            artifacts_root=tmp_path / "r" / "artifacts",
            payloads_root=tmp_path / "r" / "payloads",
        )
        assert restored.payload_files == 0


class TestTheCommandUsesTheConfiguredRoot:
    def test_backup_reads_the_payload_setting_and_reports_it(
        self, machine, tmp_path, monkeypatch, capsys
    ):
        db, artifacts, payloads = machine
        monkeypatch.setenv(config.ENV_PAYLOADS, str(payloads))

        code = main(
            ["--db", str(db), "--artifacts", str(artifacts),
             "backup", "--to", str(tmp_path / "out"), "--same-device-ok"]
        )

        assert code == 0
        assert "payloads    2 files" in capsys.readouterr().out

    def test_an_explicit_override_wins(self, machine, tmp_path, capsys):
        db, artifacts, payloads = machine

        code = main(
            ["--db", str(db), "--artifacts", str(artifacts),
             "--payloads", str(payloads),
             "backup", "--to", str(tmp_path / "out"), "--same-device-ok"]
        )

        assert code == 0
        assert "payloads    2 files" in capsys.readouterr().out
