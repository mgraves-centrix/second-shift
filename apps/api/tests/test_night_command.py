"""`python -m secondshift.night run`, driven end to end.

The command had never been called by a test — the pieces it wires together
were each tested, and the wiring was not. Every test here goes through `main`,
with the model, the brain and the probe replaced at the command's own seams
and everything else real: migrations, the roster, prompts, pricing, the
database and the artifact files.
"""

from __future__ import annotations

import sqlite3

import pytest

from secondshift.config import Profile, ProbeResult, ProfileSource, ResolvedProfile
from secondshift.db import connection, migrate
from secondshift.db.connection import now_ms
from secondshift.db.repository import Repository
from secondshift.night import __main__ as cli
from secondshift.night import run as night_run
from secondshift.providers.base import RawCompletion, Reasoner
from secondshift.providers.registry import Providers


class Stub(Reasoner):
    provider_kind = "local-vllm"

    def __init__(self, recorder) -> None:
        super().__init__(recorder, model="stub")

    def _do_complete(self, messages, *, effort) -> RawCompletion:
        return RawCompletion(
            text="a considered answer",
            prompt_tokens=5,
            completion_tokens=7,
            reasoning_tokens=0,
            cache_hit=False,
            finish_reason="stop",
        )


@pytest.fixture
def db_path(tmp_path):
    path = tmp_path / "night.db"
    conn = connection.connect(path)
    migrate.migrate(conn)
    conn.close()
    return path


@pytest.fixture
def command(monkeypatch, tmp_path):
    """The command with its machine-specific seams replaced. Returns a setter
    for the profile, so a test can run it as a `cloud` deployment."""
    state = {"profile": Profile.SPARK}

    def resolve_profile():
        degraded = state["profile"] is Profile.CLOUD
        return ResolvedProfile(
            profile=state["profile"],
            source=ProfileSource.PROBE,
            probe=ProbeResult({}),
            degraded=degraded,
            degradation_reason="no local reasoner answered" if degraded else None,
        )

    class Registry:
        def __init__(self, recorder) -> None:
            self._recorder = recorder

        def bind(self, profile):
            return Providers(
                reasoner=Stub(self._recorder),
                transcriber=None,  # type: ignore[arg-type]
                embedder=None,  # type: ignore[arg-type]
                executor=None,  # type: ignore[arg-type]
            )

    class NoBrain:
        available = False

    monkeypatch.setattr(cli, "resolve_profile", resolve_profile)
    monkeypatch.setattr(cli, "Registry", Registry)
    monkeypatch.setattr(cli, "BrainRepo", NoBrain)
    monkeypatch.setattr(cli, "artifact_root", lambda: tmp_path / "artifacts")
    return lambda profile: state.__setitem__("profile", profile)


def _open(db_path) -> tuple[sqlite3.Connection, Repository]:
    conn = connection.connect(db_path)
    return conn, Repository(conn)


def _queue(db_path, text: str = "a weekly digest of my voice notes") -> str:
    conn, repo = _open(db_path)
    try:
        return repo.insert_entry(
            created_at_ms=now_ms(),
            captured_tz="UTC",
            tz_offset_min=0,
            modality="text",
            default_policy="cloud-assisted",
            status="queued",
            capture_profile="spark",
            raw_text=text,
        )
    finally:
        conn.close()


def _status(db_path, entry_id: str) -> str:
    conn, repo = _open(db_path)
    try:
        return repo.get_entry(entry_id)["status"]
    finally:
        conn.close()


def _scalar(db_path, sql: str, *args):
    conn, _ = _open(db_path)
    try:
        return conn.execute(sql, args).fetchone()[0]
    finally:
        conn.close()


class TestANightRuns:
    def test_the_command_works_an_entry_and_closes_its_run(
        self, db_path, command, capsys
    ):
        entry = _queue(db_path)

        assert cli.main(["run", "--db", str(db_path)]) == 0

        assert _status(db_path, entry) == "answered"
        assert _scalar(db_path, "SELECT COUNT(*) FROM runs WHERE ended_at_ms IS NULL") == 0
        assert "stages complete" in capsys.readouterr().out

    def test_one_entry_s_defect_does_not_end_the_night(
        self, db_path, command, monkeypatch, capsys
    ):
        """An exception that escaped one entry used to propagate out of `main`,
        and every entry after it never ran."""
        first = _queue(db_path, "the first idea")
        second = _queue(db_path, "the second idea")
        real = cli.run_entry

        def run_entry(repo, recorder, providers, row, **kwargs):
            if row["id"] == first:
                raise ValueError("embedding dimension mismatch")
            return real(repo, recorder, providers, row, **kwargs)

        monkeypatch.setattr(cli, "run_entry", run_entry)

        assert cli.main(["run", "--db", str(db_path)]) == 1

        assert _status(db_path, second) == "answered"
        assert _status(db_path, first) == "queued"
        out = capsys.readouterr()
        assert first in out.err and "embedding dimension mismatch" in out.err


class TestNoSilentSubstitute:
    """On `cloud` the registry binds an echo reasoner labeled `local-vllm`. The
    night ran every `cloud-assisted` idea against it, closed the stages
    `complete` with the prompt echoed back as the artifact, and moved the ideas
    to `answered` — so the first night after a reboot, before the model servers
    came up, could consume every idea with fabricated output."""

    def test_a_cloud_deployment_with_no_cloud_reasoner_refuses_to_start(
        self, db_path, command, capsys
    ):
        command(Profile.CLOUD)
        entry = _queue(db_path)

        assert cli.main(["run", "--db", str(db_path)]) == 2

        assert _status(db_path, entry) == "queued"
        assert _scalar(db_path, "SELECT COUNT(*) FROM runs") == 0
        assert "no local reasoner answered" in capsys.readouterr().err


    def test_a_backend_that_cannot_be_bound_refuses_rather_than_crashing(
        self, db_path, command, monkeypatch, capsys
    ):
        """Binding raised outside any handler, so a missing model name ended
        the command with a traceback instead of saying what to set."""
        from secondshift.providers.registry import LocalReasonerNotConfigured

        class Unconfigured:
            def __init__(self, recorder) -> None:
                pass

            def bind(self, profile):
                raise LocalReasonerNotConfigured("set SECOND_SHIFT_LOCAL_MODEL")

        monkeypatch.setattr(cli, "Registry", Unconfigured)
        entry = _queue(db_path)

        assert cli.main(["run", "--db", str(db_path)]) == 2

        assert _status(db_path, entry) == "queued"
        assert "set SECOND_SHIFT_LOCAL_MODEL" in capsys.readouterr().err


class TestAnInterruptedNight:
    """A night killed mid-run skips the `finally` that closes it. The entry
    stayed `running`, which nothing dispatches and nothing lists, so the idea
    disappeared from both the night and the report of what was not run."""

    def _interrupt(self, db_path) -> tuple[str, str]:
        entry = _queue(db_path)
        conn, repo = _open(db_path)
        try:
            repo.transition_entry(entry, to_status="running")
            run = repo.insert_run(
                entry_id=entry,
                night_of="2026-09-02",
                effective_policy="cloud-assisted",
                policy_source="entry-default",
                compute_profile="spark",
            )
            repo.insert_run_stage(
                run_id=run, stage="brief", seq=1, status="running", started_at_ms=now_ms()
            )
        finally:
            conn.close()
        return entry, run

    def test_the_next_night_closes_what_was_left_open(self, db_path, command, capsys):
        entry, run = self._interrupt(db_path)

        assert cli.main(["run", "--db", str(db_path)]) == 0

        assert _scalar(db_path, "SELECT outcome FROM runs WHERE id = ?", run) == "failed"
        assert _scalar(
            db_path, "SELECT COUNT(*) FROM run_stages WHERE ended_at_ms IS NULL"
        ) == 0
        assert run in capsys.readouterr().out

    def test_the_idea_is_worked_again_rather_than_lost(self, db_path, command):
        entry, run = self._interrupt(db_path)

        cli.main(["run", "--db", str(db_path)])

        assert _status(db_path, entry) == "answered"
        assert _scalar(
            db_path, "SELECT COUNT(*) FROM runs WHERE entry_id = ?", entry
        ) == 2

    def test_a_night_already_running_is_not_recovered_out_from_under_itself(
        self, db_path, command, capsys
    ):
        """Recovery closes open runs, so it is only safe when no other night
        holds them. A second command refuses rather than recovering."""
        entry, run = self._interrupt(db_path)

        with cli.night_lock(db_path):
            assert cli.main(["run", "--db", str(db_path)]) == 3

        assert _scalar(db_path, "SELECT ended_at_ms FROM runs WHERE id = ?", run) is None
        assert _status(db_path, entry) == "running"
        assert "already running" in capsys.readouterr().err


class TestAStageThatWroteNothing:
    def test_a_fan_out_with_no_file_landed_is_not_complete(
        self, db_path, command, monkeypatch
    ):
        """`write_variants` catches each write failure and returns normally, so
        a full disk closed `build` as `complete` with zero artifacts — the
        morning promising work it cannot open."""
        from secondshift.artifacts import variants
        from secondshift.artifacts.store import ArtifactWriteFailed

        def disk_full(*args, **kwargs):
            raise ArtifactWriteFailed("No space left on device")

        monkeypatch.setattr(variants, "write_artifact", disk_full)
        _queue(db_path)

        cli.main(["run", "--db", str(db_path)])

        assert _scalar(
            db_path,
            "SELECT status FROM run_stages WHERE stage = 'build'",
        ) == "failed"

    def test_an_unexpected_error_writing_output_fails_the_stage_not_the_night(
        self, db_path, command, monkeypatch
    ):
        """`_run_stage` says it never raises, and caught only
        `ArtifactWriteFailed`; anything else left the stage row `running`."""

        def broken(*args, **kwargs):
            raise sqlite3.IntegrityError("constraint failed")

        monkeypatch.setattr(night_run, "write_output", broken)
        entry = _queue(db_path)

        assert cli.main(["run", "--db", str(db_path)]) == 0

        assert _scalar(
            db_path, "SELECT COUNT(*) FROM run_stages WHERE status = 'running'"
        ) == 0
        assert _scalar(
            db_path, "SELECT COUNT(*) FROM runs WHERE ended_at_ms IS NULL"
        ) == 0
        assert _status(db_path, entry) == "queued"
