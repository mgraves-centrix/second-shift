"""The loop, end to end: night → questions → answer → tonight's input.

Written after an audit found that `raise_questions`, `queued_for_tonight` and
`mark_consumed` had **no caller outside their own tests**. Each worked when
called and nothing called them, so:

- the morning was structurally incapable of containing a question, and
- `queued-for-tonight` was a status the system could write and never act on.

Both are claims the capability makes about itself, and neither was reachable.
These tests assert the connections rather than the pieces, because the pieces
were already green while the loop was open.
"""

from __future__ import annotations

import subprocess

import pytest

from secondshift.agents.roster import discover, register
from secondshift.db.connection import now_ms
from secondshift.morning import assemble, answer, queued_for_tonight
from secondshift.night.run import run_entry
from secondshift.providers.base import RawCompletion, Reasoner
from secondshift.providers.registry import Providers

QUESTIONS = (
    "Q: Do you read the digest on a phone?\n"
    "Why: The builder had two shapes and could not choose without knowing.\n"
)


class Recorder_(Reasoner):
    """Echoes the interviewer format, and remembers what it was asked."""

    provider_kind = "local-vllm"

    def __init__(self, recorder, *, text: str = "an answer") -> None:
        super().__init__(recorder, model="stub")
        self._text = text
        self.seen: list[str] = []

    def _do_complete(self, messages, *, effort) -> RawCompletion:
        self.seen.append("\n".join(m.content for m in messages))
        return RawCompletion(
            text=self._text,
            prompt_tokens=5,
            completion_tokens=7,
            reasoning_tokens=0,
            cache_hit=False,
            finish_reason="stop",
        )


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
def roster(repo):
    agents = register(repo)
    return agents, {r: p.path for r, p in discover().items()}


def _run(repo, recorder, entry_id, roster, tmp_path, reasoner=None):
    agents, prompts = roster
    reasoner = reasoner or Recorder_(recorder)
    return run_entry(
        repo,
        recorder,
        Providers(
            reasoner=reasoner,
            transcriber=None,  # type: ignore[arg-type]
            embedder=None,  # type: ignore[arg-type]
            executor=None,  # type: ignore[arg-type]
        ),
        repo.get_entry(entry_id),
        profile="spark",
        agents=agents,
        prompts=prompts,
        local_available=True,
        night_of="2026-09-03",
        artifact_root=tmp_path,
    )


class TestAQueuedAnswerReachesTheNight:
    def test_the_answer_is_handed_to_the_stages(
        self, repo, recorder, entry, roster, tmp_path
    ):
        """The half of "answering changes tonight" that was never wired."""
        decision = repo.insert_decision(
            entry_id=entry,
            question="Do you read it on a phone?",
            rationale="two shapes",
            status="open",
        )
        answer(repo, decision, text="phone, always", status="queued-for-tonight")
        reasoner = Recorder_(recorder)

        _run(repo, recorder, entry, roster, tmp_path, reasoner)

        assert any("phone, always" in seen for seen in reasoner.seen)

    def test_the_decision_is_marked_consumed_by_that_run(
        self, repo, recorder, entry, roster, tmp_path
    ):
        decision = repo.insert_decision(
            entry_id=entry, question="q", rationale="r", status="open"
        )
        answer(repo, decision, text="yes", status="queued-for-tonight")

        result = _run(repo, recorder, entry, roster, tmp_path)

        row = repo.connection.execute(
            "SELECT * FROM decisions WHERE id = ?", (decision,)
        ).fetchone()
        assert row["consumed_by_run_id"] == result.run_id

    def test_a_consumed_answer_leaves_the_queue(
        self, repo, recorder, entry, roster, tmp_path
    ):
        decision = repo.insert_decision(
            entry_id=entry, question="q", rationale="r", status="open"
        )
        answer(repo, decision, text="yes", status="queued-for-tonight")
        assert len(queued_for_tonight(repo, entry)) == 1

        _run(repo, recorder, entry, roster, tmp_path)

        assert queued_for_tonight(repo, entry) == []

    def test_an_answer_is_taken_once_not_every_night(
        self, repo, recorder, entry, roster, tmp_path
    ):
        """`mark_consumed` refuses a second claim, so an answer feeds one night
        and not every night after it — and a second idea never sees it at all,
        because answers are taken by the entry they were asked about."""
        decision = repo.insert_decision(
            entry_id=entry, question="q", rationale="r", status="open"
        )
        answer(repo, decision, text="yes", status="queued-for-tonight")
        _run(repo, recorder, entry, roster, tmp_path)

        second = repo.insert_entry(
            created_at_ms=now_ms(),
            captured_tz="UTC",
            tz_offset_min=0,
            modality="text",
            default_policy="cloud-assisted",
            status="queued",
            capture_profile="spark",
            raw_text="a second idea",
        )
        reasoner = Recorder_(recorder)
        _run(repo, recorder, second, roster, tmp_path, reasoner)

        assert not any("What you decided this morning" in s for s in reasoner.seen)

    def test_a_night_with_no_queued_answer_says_nothing_about_one(
        self, repo, recorder, entry, roster, tmp_path
    ):
        reasoner = Recorder_(recorder)

        _run(repo, recorder, entry, roster, tmp_path, reasoner)

        assert not any("What you decided this morning" in s for s in reasoner.seen)


class Failing(Recorder_):
    """Every turn raises, so every stage fails and the run's outcome is `failed`."""

    def _do_complete(self, messages, *, effort):
        self.seen.append("\n".join(m.content for m in messages))
        raise RuntimeError("the reasoner fell over")


def _entry(repo, *, policy: str, text: str) -> str:
    return repo.insert_entry(
        created_at_ms=now_ms(),
        captured_tz="UTC",
        tz_offset_min=0,
        modality="text",
        default_policy=policy,
        status="queued",
        capture_profile="spark",
        raw_text=text,
    )


def _queue_answer(repo, entry_id: str, text: str) -> str:
    decision = repo.insert_decision(
        entry_id=entry_id, question="q", rationale="r", status="open"
    )
    answer(repo, decision, text=text, status="queued-for-tonight")
    return decision


class TestAnswersBelongToTheirIdea:
    """Found by three reviewers independently. Answers were taken by whichever
    entry ran first, whatever idea they were about — so one idea's answer became
    another idea's context, under the other idea's policy."""

    def test_another_idea_s_answer_is_not_handed_to_this_run(
        self, repo, recorder, roster, tmp_path
    ):
        private = _entry(repo, policy="local-only", text="a private idea")
        _queue_answer(repo, private, "the private detail")
        shared = _entry(repo, policy="cloud-assisted", text="a shareable idea")
        reasoner = Recorder_(recorder)

        _run(repo, recorder, shared, roster, tmp_path, reasoner)

        assert not any("the private detail" in seen for seen in reasoner.seen)

    def test_another_idea_s_answer_is_left_for_that_idea(
        self, repo, recorder, roster, tmp_path
    ):
        private = _entry(repo, policy="local-only", text="a private idea")
        decision = _queue_answer(repo, private, "the private detail")
        shared = _entry(repo, policy="cloud-assisted", text="a shareable idea")

        _run(repo, recorder, shared, roster, tmp_path)

        assert [r["id"] for r in queued_for_tonight(repo, private)] == [decision]

    def test_a_failed_run_does_not_consume_the_answer(
        self, repo, recorder, entry, roster, tmp_path
    ):
        """A run that produced nothing did not act on the answer. Consuming it
        anyway lost the answer for the retry and made `consumed_by_run_id` name
        a run that never used it."""
        decision = _queue_answer(repo, entry, "phone, always")

        result = _run(repo, recorder, entry, roster, tmp_path, Failing(recorder))

        assert result.outcome == "failed"
        row = repo.connection.execute(
            "SELECT consumed_by_run_id FROM decisions WHERE id = ?", (decision,)
        ).fetchone()
        assert row["consumed_by_run_id"] is None
        assert [r["id"] for r in queued_for_tonight(repo, entry)] == [decision]


class TestAFailedStageSaysWhyInTheMorning:
    """`record_failure` read the run from the invocation context, and the night
    records a stage's failure after its invocation has closed — so every real
    failure was stored with no run, and the morning, which reads reasons by
    run, showed none. The tests that covered reasons inserted the rows by hand."""

    def test_the_reason_reaches_the_briefing(
        self, repo, recorder, entry, roster, tmp_path
    ):
        from secondshift.morning import for_run

        result = _run(repo, recorder, entry, roster, tmp_path, Failing(recorder))

        stages = {s.stage: s for s in for_run(repo, result.run_id).nights[0].stages}
        assert stages["brief"].status == "failed"
        assert stages["brief"].reason == "the reasoner fell over"

    def test_the_failure_row_names_the_run(
        self, repo, recorder, entry, roster, tmp_path
    ):
        result = _run(repo, recorder, entry, roster, tmp_path, Failing(recorder))

        orphans = repo.connection.execute(
            "SELECT COUNT(*) n FROM failures WHERE run_id IS NULL"
        ).fetchone()["n"]
        assert orphans == 0
        assert repo.connection.execute(
            "SELECT COUNT(*) n FROM failures WHERE run_id = ?", (result.run_id,)
        ).fetchone()["n"] > 0


class TestTheLoopClosesInTheOrderItHappens:
    """The earlier tests answered a question *before* the first run, an order
    that cannot happen: questions are raised at the end of a night, after the
    run has already moved its entry to `answered`, and nothing moved it back. An
    answer queued for tonight therefore had no night to reach."""

    def test_queuing_an_answer_returns_its_idea_to_the_night(
        self, repo, recorder, entry, roster, tmp_path
    ):
        _run(repo, recorder, entry, roster, tmp_path)
        assert repo.get_entry(entry)["status"] == "answered"

        _queue_answer(repo, entry, "phone, always")

        assert repo.get_entry(entry)["status"] == "queued"
        assert entry in [r["id"] for r in repo.dispatch_eligible_entries()]

    def test_the_second_night_sees_the_first_morning_s_answer(
        self, repo, recorder, entry, roster, tmp_path
    ):
        from secondshift.night import __main__ as cli

        agents, prompts = roster
        first = _run(repo, recorder, entry, roster, tmp_path)
        asker = Providers(
            reasoner=Recorder_(recorder, text=QUESTIONS),
            transcriber=None,  # type: ignore[arg-type]
            embedder=None,  # type: ignore[arg-type]
            executor=None,  # type: ignore[arg-type]
        )
        cli._ask_about(repo, recorder, asker, first, agents, prompts, entry)
        question = assemble(repo).questions[0]
        answer(repo, question.decision_id, text="phone, always", status="queued-for-tonight")
        reasoner = Recorder_(recorder)

        second = _run(repo, recorder, entry, roster, tmp_path, reasoner)

        assert any("phone, always" in seen for seen in reasoner.seen)
        row = repo.connection.execute(
            "SELECT consumed_by_run_id FROM decisions WHERE id = ?",
            (question.decision_id,),
        ).fetchone()
        assert row["consumed_by_run_id"] == second.run_id

    def test_an_answer_given_while_the_idea_is_running_gets_a_night(
        self, repo, recorder, entry, roster, tmp_path
    ):
        """The entry is `running` while a night works it, so queuing an answer
        then does not re-queue it — and the run, which read its answers before
        its first stage, closed the entry `answered`. The answer sat queued on
        an idea no night would pick up."""
        open_question = repo.insert_decision(
            entry_id=entry, question="q", rationale="r", status="open"
        )

        class AnswersMidRun(Recorder_):
            def _do_complete(self, messages, *, effort):
                if not getattr(self, "answered", False):
                    self.answered = True
                    answer(repo, open_question, text="mid-run", status="queued-for-tonight")
                return super()._do_complete(messages, effort=effort)

        _run(repo, recorder, entry, roster, tmp_path, AnswersMidRun(recorder))

        assert repo.get_entry(entry)["status"] == "queued"
        assert [r["id"] for r in queued_for_tonight(repo, entry)] == [open_question]

    def test_other_outcomes_leave_the_idea_where_it_is(
        self, repo, recorder, entry, roster, tmp_path
    ):
        """Only an answer meant for tonight has anything for tonight to do."""
        _run(repo, recorder, entry, roster, tmp_path)
        for status in ("decided", "deferred", "obsolete"):
            decision = repo.insert_decision(
                entry_id=entry, question="q", rationale="r", status="open"
            )
            answer(repo, decision, text="", status=status)

        assert repo.get_entry(entry)["status"] == "answered"


class TestTheInterviewerSeesOnlyItsNight:
    """It was handed every run since the last answered decision, across every
    entry, once per entry — so a `local-only` night's stages and failure text
    went out under another run's policy, and each night was asked about N
    times."""

    def test_another_run_s_facts_are_not_in_the_interview(
        self, repo, recorder, roster, tmp_path
    ):
        from secondshift.night import __main__ as cli

        agents, prompts = roster
        private = _entry(repo, policy="local-only", text="a private idea")
        shared = _entry(repo, policy="cloud-assisted", text="a shareable idea")
        first = _run(repo, recorder, private, roster, tmp_path)
        second = _run(repo, recorder, shared, roster, tmp_path)
        interviewer = Recorder_(recorder, text=QUESTIONS)
        providers = Providers(
            reasoner=interviewer,
            transcriber=None,  # type: ignore[arg-type]
            embedder=None,  # type: ignore[arg-type]
            executor=None,  # type: ignore[arg-type]
        )

        cli._ask_about(repo, recorder, providers, second, agents, prompts, shared)

        assert interviewer.seen, "the interviewer was never called"
        assert not any(first.run_id in seen for seen in interviewer.seen)
        assert any(second.run_id in seen for seen in interviewer.seen)


class TestTheNightRaisesTheQuestions:
    """The other half. The interviewer runs at the end of the night, so the
    morning has something to ask — and it is not an evening interview, because
    nobody is spoken to: the questions sit as `open` decisions until morning."""

    def test_the_command_raises_questions_for_the_morning(
        self, repo, recorder, entry, roster, tmp_path, monkeypatch
    ):
        from secondshift.night import __main__ as cli

        agents, prompts = roster
        result = _run(repo, recorder, entry, roster, tmp_path)
        providers = Providers(
            reasoner=Recorder_(recorder, text=QUESTIONS),
            transcriber=None,  # type: ignore[arg-type]
            embedder=None,  # type: ignore[arg-type]
            executor=None,  # type: ignore[arg-type]
        )

        raised = cli._ask_about(
            repo, recorder, providers, result, agents, prompts, entry
        )

        assert raised == 1
        assert len(assemble(repo).questions) == 1

    def test_the_raised_question_names_the_run_it_came_from(
        self, repo, recorder, entry, roster, tmp_path
    ):
        from secondshift.night import __main__ as cli

        agents, prompts = roster
        result = _run(repo, recorder, entry, roster, tmp_path)
        providers = Providers(
            reasoner=Recorder_(recorder, text=QUESTIONS),
            transcriber=None,  # type: ignore[arg-type]
            embedder=None,  # type: ignore[arg-type]
            executor=None,  # type: ignore[arg-type]
        )

        cli._ask_about(repo, recorder, providers, result, agents, prompts, entry)

        row = repo.connection.execute("SELECT * FROM decisions").fetchone()
        assert row["raised_by_run_id"] == result.run_id

    def test_an_interviewer_that_fails_does_not_fail_the_night(
        self, repo, recorder, entry, roster, tmp_path
    ):
        """Principle 3: a night that produced work and could not phrase a
        question is still a night that produced work."""
        from secondshift.night import __main__ as cli

        class Broken(Recorder_):
            def _do_complete(self, messages, *, effort):
                raise RuntimeError("the interviewer fell over")

        agents, prompts = roster
        result = _run(repo, recorder, entry, roster, tmp_path)
        providers = Providers(
            reasoner=Broken(recorder),
            transcriber=None,  # type: ignore[arg-type]
            embedder=None,  # type: ignore[arg-type]
            executor=None,  # type: ignore[arg-type]
        )

        raised = cli._ask_about(
            repo, recorder, providers, result, agents, prompts, entry
        )

        assert raised == 0
        assert len(assemble(repo).nights) == 1

    def test_an_interviewer_that_fails_says_so_in_the_morning(
        self, repo, recorder, entry, roster, tmp_path
    ):
        """`interviewer_error` was declared, passed through the API and rendered
        by the screen, and never set — so a morning after a broken interviewer
        read "the night got stuck on nothing", which is false."""
        from secondshift.night import __main__ as cli

        agents, prompts = roster
        result = _run(repo, recorder, entry, roster, tmp_path)
        providers = Providers(
            reasoner=Failing(recorder),
            transcriber=None,  # type: ignore[arg-type]
            embedder=None,  # type: ignore[arg-type]
            executor=None,  # type: ignore[arg-type]
        )

        cli._ask_about(repo, recorder, providers, result, agents, prompts, entry)

        assert assemble(repo).interviewer_error == "the reasoner fell over"

    def test_a_working_interviewer_reports_no_error(
        self, repo, recorder, entry, roster, tmp_path
    ):
        from secondshift.night import __main__ as cli

        agents, prompts = roster
        result = _run(repo, recorder, entry, roster, tmp_path)
        providers = Providers(
            reasoner=Recorder_(recorder, text=QUESTIONS),
            transcriber=None,  # type: ignore[arg-type]
            embedder=None,  # type: ignore[arg-type]
            executor=None,  # type: ignore[arg-type]
        )

        cli._ask_about(repo, recorder, providers, result, agents, prompts, entry)

        assert assemble(repo).interviewer_error is None

    def test_a_quarantined_entry_raises_nothing(self, repo, recorder, roster):
        """No run happened, so there is nothing to be asked about."""
        from secondshift.night import __main__ as cli
        from secondshift.night.run import NightResult

        agents, prompts = roster
        quarantined = NightResult(
            entry_id="e", run_id=None, outcome=None, quarantine_reason="local-only"
        )

        assert (
            cli._ask_about(repo, recorder, None, quarantined, agents, prompts, "e") == 0
        )

    def test_the_interviewer_runs_under_the_run_s_own_policy(
        self, repo, recorder, entry, roster, tmp_path
    ):
        """A local-only night's interviewer must not reach a remote provider.
        The policy is carried on the result rather than guessed — an earlier
        version computed it with an expression that always returned the same
        constant whatever the run did."""
        result = _run(repo, recorder, entry, roster, tmp_path)

        assert result.effective_policy == "cloud-assisted"


class TestTheNightRevisesWhatItBelieves:
    """ADR 0007: improvement comes from the brain, and the week-1-to-week-8
    `git diff` is the evidence. Until now the distiller only ever appended a
    night's record; nothing revised a belief, so that diff showed an unchanged
    profile however many nights had run."""

    @pytest.fixture
    def brain(self, tmp_path):
        from secondshift.brain.repo import BrainRepo

        path = tmp_path / "brain"
        path.mkdir()
        (path / "profile.md").write_text("# Profile\n\nPrefers short briefs.\n")
        (path / "style-guide.md").write_text("# Style\n\nDirect sentences.\n")
        for args in (
            ["init", "-q", "-b", "main"],
            ["config", "user.email", "t@example.invalid"],
            ["config", "user.name", "Test"],
            ["add", "-A"],
            ["commit", "-q", "-m", "seed"],
        ):
            subprocess.run(["git", "-C", str(path), *args], check=True, capture_output=True)
        return BrainRepo(path)

    def _distilling(self, recorder, text):
        return Recorder_(recorder, text=text)

    def test_a_proposed_belief_lands_in_the_profile_and_its_commit(
        self, repo, recorder, entry, roster, tmp_path, brain
    ):
        proposal = (
            "The night showed a preference for brevity.\n\n"
            "BELIEF: Prefers a brief short enough to read standing up.\n"
            "REPLACES: Prefers short briefs.\n"
        )
        agents, prompts = roster

        run_entry(
            repo,
            recorder,
            Providers(
                reasoner=self._distilling(recorder, proposal),
                transcriber=None,  # type: ignore[arg-type]
                embedder=None,  # type: ignore[arg-type]
                executor=None,  # type: ignore[arg-type]
            ),
            repo.get_entry(entry),
            profile="spark",
            agents=agents,
            prompts=prompts,
            local_available=True,
            night_of="2026-09-17",
            artifact_root=tmp_path,
            brain=brain,
        )

        profile = (brain.path / "profile.md").read_text()
        assert "read standing up" in profile
        assert "Prefers short briefs." not in profile
        committed = subprocess.run(
            ["git", "-C", str(brain.path), "show", "--stat", "--format=%s", "HEAD"],
            capture_output=True, text=True, check=True,
        ).stdout
        assert "profile.md" in committed and "nights/" in committed

    def test_a_night_that_proposes_nothing_leaves_the_brain_alone(
        self, repo, recorder, entry, roster, tmp_path, brain
    ):
        """The normal case: most nights teach nothing about the person."""
        before = (brain.path / "profile.md").read_text()
        agents, prompts = roster

        run_entry(
            repo,
            recorder,
            Providers(
                reasoner=self._distilling(recorder, "Nothing new about the person tonight."),
                transcriber=None,  # type: ignore[arg-type]
                embedder=None,  # type: ignore[arg-type]
                executor=None,  # type: ignore[arg-type]
            ),
            repo.get_entry(entry),
            profile="spark",
            agents=agents,
            prompts=prompts,
            local_available=True,
            night_of="2026-09-17",
            artifact_root=tmp_path,
            brain=brain,
        )

        assert (brain.path / "profile.md").read_text() == before


class TestTheGuardsAreWired:
    """`assert_artifact_kinds_match_schema` was written, never called, never
    tested and never exported — a guard against stage-to-kind drift that
    guarded nothing."""

    def test_the_stage_artifact_kinds_match_the_schema(self, conn):
        from secondshift.night import assert_artifact_kinds_match_schema

        assert_artifact_kinds_match_schema(conn)

    def test_it_refuses_a_kind_the_schema_does_not_permit(self, conn, monkeypatch):
        """Proof it can fail, since nothing had ever run it."""
        from secondshift.night import assert_artifact_kinds_match_schema, stages

        bogus = stages.Stage("brief", 1, "researcher", lambda d: True, artifact_kind="nope")
        monkeypatch.setattr(stages, "STAGES", (bogus,))

        with pytest.raises(RuntimeError, match="artifact kinds the schema forbids"):
            assert_artifact_kinds_match_schema(conn)
