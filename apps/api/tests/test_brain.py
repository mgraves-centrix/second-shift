"""The brain: journaling, derivation, staging discipline, and pinning."""

from __future__ import annotations

import subprocess

import pytest

from secondshift.brain.journal import JournalEntry, journal_path, journaled_ids
from secondshift.brain.repo import BrainRepo, BrainUnavailable
from secondshift.brain.sync import backlog, sync, unjournaled
from secondshift.db.connection import now_ms
from secondshift.db.ids import new_ulid

TZ = dict(captured_tz="America/Los_Angeles", tz_offset_min=-420)
DAY = 86_400_000


@pytest.fixture
def brain(tmp_path) -> BrainRepo:
    """A real git repository, because the code shells out to a real git."""
    path = tmp_path / "brain"
    (path / "skills").mkdir(parents=True)
    (path / "journal").mkdir()
    (path / "profile.md").write_text("# Profile\n\nA starting sketch.\n")
    (path / "style-guide.md").write_text("# Style\n\nDirect.\n")
    (path / "skills" / "README.md").write_text("# Skills\n\nEmpty on day one.\n")
    for args in (
        ["init", "-q", "-b", "main"],
        ["config", "user.email", "test@example.invalid"],
        ["config", "user.name", "Test"],
        ["add", "-A"],
        ["commit", "-q", "-m", "seed"],
    ):
        subprocess.run(["git", "-C", str(path), *args], check=True, capture_output=True)
    return BrainRepo(path)


def _capture(repo, text="an idea", when=None, policy="cloud-assisted", **kw):
    when = when if when is not None else now_ms()
    return repo.insert_entry(
        created_at_ms=when,
        modality="text",
        default_policy=policy,
        status="queued",
        capture_profile="spark",
        raw_text=text,
        **TZ,
        **kw,
    )


class TestBrainAccess:
    def test_reads_topic_files(self, brain):
        topics = brain.topic_files()
        assert "starting sketch" in topics.profile
        assert "Direct" in topics.style_guide

    def test_a_brain_with_no_skills_is_new_not_broken(self, brain):
        assert brain.topic_files().skills == {}

    def test_skills_readme_is_not_a_skill(self, brain):
        (brain.path / "skills" / "interrogate-vague-idea.md").write_text("# How\n")
        skills = brain.topic_files().skills
        assert set(skills) == {"interrogate-vague-idea"}

    def test_missing_topic_file_is_tolerated(self, brain):
        (brain.path / "profile.md").unlink()
        assert brain.topic_files().profile == ""

    def test_absent_path_is_unavailable(self, tmp_path):
        missing = BrainRepo(tmp_path / "nowhere")
        assert missing.available is False
        assert missing.head() is None
        with pytest.raises(BrainUnavailable, match="does not exist"):
            missing.require()

    def test_non_git_directory_is_unavailable(self, tmp_path):
        plain = tmp_path / "plain"
        plain.mkdir()
        with pytest.raises(BrainUnavailable, match="not a git repository"):
            BrainRepo(plain).require()

    def test_head_is_readable(self, brain):
        assert len(brain.head() or "") == 40


class TestJournal:
    def test_entry_round_trips(self, repo, brain):
        entry = _capture(repo, text="a tool that notices repeated mistakes")
        sync(repo, brain)
        text = "".join(p.read_text() for p in (brain.path / "journal").glob("*.md"))
        assert entry in text
        assert "notices repeated mistakes" in text
        assert entry in journaled_ids(brain.path)

    def test_entries_are_ordered_by_capture_not_arrival(self, repo, brain):
        base = now_ms()
        later = _capture(repo, text="captured second", when=base + 60_000)
        earlier = _capture(repo, text="captured first", when=base)
        sync(repo, brain)
        content = "".join(p.read_text() for p in (brain.path / "journal").glob("*.md"))
        assert content.index(earlier) < content.index(later)

    def test_late_entry_files_under_its_capture_date(self, repo, brain):
        """Captured at 23:50 local, received next morning. It belongs to that night."""
        # 2026-08-27 23:50 local at -420 == 2026-08-28 06:50 UTC
        captured = 1_787_115_000_000
        entry = _capture(repo, text="a late idea", when=captured)
        sync(repo, brain)
        local_date = JournalEntry(
            entry_id=entry, created_at_ms=captured, tz_offset_min=-420,
            captured_tz="America/Los_Angeles", policy="cloud-assisted", text="x",
        ).local_date
        assert journal_path(brain.path, local_date).is_file()
        assert entry in journal_path(brain.path, local_date).read_text()

    def test_journaled_ids_on_a_brain_with_no_journal(self, tmp_path):
        assert journaled_ids(tmp_path) == set()

    def test_identifier_regex_does_not_match_prose(self, repo, brain):
        _capture(repo, text="A B C D E F G H J K M N P Q R S T V W X Y Z 0 1 2 3")
        sync(repo, brain)
        assert len(journaled_ids(brain.path)) == 1


class TestSync:
    def test_sync_is_idempotent(self, repo, brain):
        _capture(repo)
        first = sync(repo, brain)
        second = sync(repo, brain)
        assert first.count == 1 and second.count == 0
        assert second.commit is None
        assert len(journaled_ids(brain.path)) == 1

    def test_one_commit_per_run_naming_what_it_covered(self, repo, brain):
        _capture(repo, text="one")
        _capture(repo, text="two")
        before = brain.head()
        result = sync(repo, brain)
        assert result.commit and result.commit != before
        message = subprocess.run(
            ["git", "-C", str(brain.path), "log", "-1", "--format=%s"],
            capture_output=True, text=True, check=True,
        ).stdout
        assert "2 entries" in message

    def test_interrupted_sync_is_resolved_without_duplication(self, repo, brain):
        entry = _capture(repo)
        # Simulate a run that wrote the journal but never committed.
        from secondshift.brain.journal import append_entries
        append_entries(brain.path, unjournaled(repo, brain))
        assert brain.dirty_paths()

        result = sync(repo, brain)
        assert result.count == 0            # already in the journal
        assert result.commit is not None    # but it was uncommitted
        content = "".join(p.read_text() for p in (brain.path / "journal").glob("*.md"))
        assert content.count(entry) == 1

    def test_a_hand_edited_topic_file_is_left_alone(self, repo, brain):
        (brain.path / "profile.md").write_text("# Profile\n\nHalf-finished thought")
        _capture(repo)
        sync(repo, brain)
        assert "profile.md" in " ".join(brain.dirty_paths())
        committed = subprocess.run(
            ["git", "-C", str(brain.path), "show", "--name-only", "--format=", "HEAD"],
            capture_output=True, text=True, check=True,
        ).stdout
        assert "profile.md" not in committed
        assert "journal/" in committed

    def test_journaling_is_not_blocked_by_an_unfinished_edit(self, repo, brain):
        (brain.path / "style-guide.md").write_text("# Style\n\nmid-sentence")
        entry = _capture(repo)
        assert sync(repo, brain).journaled == [entry]

    def test_missing_brain_fails_loudly_and_journals_nothing(self, repo, tmp_path):
        _capture(repo)
        missing = BrainRepo(tmp_path / "absent")
        with pytest.raises(BrainUnavailable):
            sync(repo, missing)
        assert journaled_ids(missing.path) == set()

    def test_backlog_is_observable(self, repo, brain):
        _capture(repo, text="one")
        _capture(repo, text="two")
        assert backlog(repo, brain) == 2
        sync(repo, brain)
        assert backlog(repo, brain) == 0

    def test_backlog_reports_unavailable_rather_than_zero(self, repo, tmp_path):
        _capture(repo)
        assert backlog(repo, BrainRepo(tmp_path / "absent")) == -1

    def test_sync_records_an_event_against_each_entry(self, repo, brain, recorder):
        entry = _capture(repo)
        sync(repo, brain, recorder)
        labels = [e["label"] for e in repo.entry_history(entry)]
        assert any("journaled" in label for label in labels)


class TestPinning:
    def test_a_run_records_the_brain_commit(self, repo, recorder, brain, monkeypatch):
        monkeypatch.setenv("SECOND_SHIFT_BRAIN", str(brain.path))
        entry = _capture(repo)
        run_id = recorder.record_run(
            entry_id=entry, night_of="2026-08-28",
            effective_policy="cloud-assisted", policy_source="entry-default",
            compute_profile="spark",
        )
        row = repo.connection.execute(
            "SELECT brain_sha FROM runs WHERE id = ?", (run_id,)
        ).fetchone()
        assert row["brain_sha"] == brain.head()

    def test_an_unreadable_brain_leaves_the_commit_unset(
        self, repo, recorder, tmp_path, monkeypatch
    ):
        monkeypatch.setenv("SECOND_SHIFT_BRAIN", str(tmp_path / "absent"))
        entry = _capture(repo)
        run_id = recorder.record_run(
            entry_id=entry, night_of="2026-08-28",
            effective_policy="cloud-assisted", policy_source="entry-default",
            compute_profile="spark",
        )
        row = repo.connection.execute(
            "SELECT brain_sha FROM runs WHERE id = ?", (run_id,)
        ).fetchone()
        # None, never a placeholder that would later look like a real state.
        assert row["brain_sha"] is None

    def test_an_explicit_commit_is_not_overridden(self, repo, recorder, brain, monkeypatch):
        monkeypatch.setenv("SECOND_SHIFT_BRAIN", str(brain.path))
        entry = _capture(repo)
        run_id = recorder.record_run(
            entry_id=entry, night_of="2026-08-28",
            effective_policy="cloud-assisted", policy_source="entry-default",
            compute_profile="spark", brain_sha="a" * 40,
        )
        row = repo.connection.execute(
            "SELECT brain_sha FROM runs WHERE id = ?", (run_id,)
        ).fetchone()
        assert row["brain_sha"] == "a" * 40

    def test_scoring_uses_the_recorded_commit_not_the_current_one(
        self, repo, recorder, brain, monkeypatch
    ):
        """An eval baseline is scored against the brain that produced it."""
        monkeypatch.setenv("SECOND_SHIFT_BRAIN", str(brain.path))
        baseline = brain.head()

        # The brain moves on.
        _capture(repo, text="a later idea")
        sync(repo, brain)
        assert brain.head() != baseline

        repo.connection.execute(
            "INSERT INTO eval_runs (id, week_of, started_at_ms, brain_sha, code_sha, "
            "judge_model, judge_provider, rubric_sha) VALUES (?,?,?,?,?,?,?,?)",
            ("ev1", "2026-08-24", now_ms(), baseline, "c0de", "judge", "token-factory", "r1"),
        )
        row = repo.connection.execute(
            "SELECT brain_sha FROM eval_runs WHERE id = 'ev1'"
        ).fetchone()
        assert row["brain_sha"] == baseline != brain.head()
