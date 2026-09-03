"""The briefing, the delta rule, and the answers.

`TestTheThreeMornings` is the load-bearing part: the open decision was settled by
writing out what the briefing says on three concrete mornings, and these are
those three. Two candidate rules were rejected there, and each rejection is a
test here — a delta since the last *night* drops the night you never read, and a
delta since you last *opened* it loses a briefing because somebody glanced at
their phone.

The mutations were run. Advancing the boundary on render turns
`test_a_night_nobody_acted_on_still_appears` red; using the latest run instead
of the last answered decision turns `test_two_nights_with_no_interview_both_appear`
red.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from secondshift.agents.roster import discover, register
from secondshift.airlock.policy import Policy, PolicySource, resolve_policy
from secondshift.db.connection import now_ms
from secondshift.morning import briefing as briefing_module
from secondshift.morning import (
    answer,
    assemble,
    boundary_ms,
    facts_for,
    mark_consumed,
    parse_questions,
    queued_for_tonight,
    raise_questions,
)
from secondshift.providers.base import Message, RawCompletion, Reasoner


class InterviewerStub(Reasoner):
    """Answers with whatever questions the test wants raised."""

    provider_kind = "local-vllm"

    def __init__(self, recorder, *, text: str = "", raises=None, **kw) -> None:
        super().__init__(recorder, model=kw.pop("model", "stub"))
        self._text = text
        self._raises = raises
        self.messages: list[Message] = []

    def _do_complete(self, messages, *, effort) -> RawCompletion:
        self.messages = list(messages)
        if self._raises is not None:
            raise self._raises
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
def night(repo, entry):
    """One run with a realistic mix: some complete, one skipped, one failed."""
    counter = {"n": 0}

    def _make(*, outcome="degraded", started_at_ms=None):
        counter["n"] += 1
        run_id = repo.insert_run(
            entry_id=entry,
            night_of="2026-09-02",
            effective_policy="cloud-assisted",
            policy_source="entry-default",
            compute_profile="spark",
            started_at_ms=started_at_ms or (now_ms() + counter["n"]),
        )
        for seq, (stage, status) in enumerate(
            [
                ("brief", "complete"),
                ("research", "skipped"),
                ("mockups", "complete"),
                ("build", "failed"),
                ("critique", "skipped"),
                ("distill", "complete"),
            ],
            start=1,
        ):
            sid = repo.insert_run_stage(
                run_id=run_id, stage=stage, seq=seq, status="running"
            )
            repo.complete_run_stage(sid, status=status)
        repo.close_run(run_id, outcome=outcome, furthest_stage="distill")
        return run_id

    return _make


@pytest.fixture
def roster(repo):
    agents = register(repo)
    prompts = {role: p.path for role, p in discover().items()}
    return agents, prompts


# -- the open decision -----------------------------------------------------


class TestTheThreeMornings:
    def test_morning_one_after_a_clean_night(self, repo, night):
        """All three candidate rules agree here. It does not discriminate, and
        it is included so the suite covers the ordinary case too."""
        night()

        result = assemble(repo)

        assert len(result.nights) == 1
        assert [s.stage for s in result.nights[0].completed] == [
            "brief",
            "mockups",
            "distill",
        ]

    def test_a_night_nobody_acted_on_still_appears(self, repo, night):
        """Morning 2, and the rejection of "since you last opened it".

        Rendering is not acting. Opening a briefing on a phone while walking is
        not the same as deciding anything, and a rule that consumed it there
        would lose the questions entirely.
        """
        night()
        first = assemble(repo)
        assert len(first.nights) == 1

        second = assemble(repo)

        assert len(second.nights) == 1, "rendering advanced the boundary"

    def test_two_nights_with_no_interview_both_appear(self, repo, night):
        """Morning 3, and the rejection of "since the last night".

        A delta since the most recent run would silently drop the earlier one —
        work the system did that nobody will ever be told about.
        """
        night()
        night()

        result = assemble(repo)

        assert len(result.nights) == 2

    def test_answering_advances_the_boundary(self, repo, entry, night):
        night()
        decision = repo.insert_decision(
            entry_id=entry, question="Which shape?", status="open", rationale="two paths"
        )
        answer(repo, decision, text="the phone-first one", status="decided")

        after = assemble(repo)

        assert after.nights == ()

    def test_deferring_counts_as_acting(self, repo, entry, night):
        """Deferring is a choice, and the prompt names it a first-class
        outcome. A rule that only counted `decided` would show the same night
        every morning until the person committed to something."""
        night()
        decision = repo.insert_decision(
            entry_id=entry, question="Which shape?", status="open", rationale="two paths"
        )
        answer(repo, decision, text="not today", status="deferred")

        assert assemble(repo).nights == ()

    def test_an_unanswered_question_does_not_advance_the_boundary(
        self, repo, entry, night
    ):
        night()
        repo.insert_decision(
            entry_id=entry, question="Which shape?", status="open", rationale="two paths"
        )

        assert len(assemble(repo).nights) == 1

    def test_the_boundary_is_zero_before_any_interview(self, repo):
        assert boundary_ms(repo) == 0


# -- principle 3 -----------------------------------------------------------


class TestAPartialNightIsPresented:
    def test_the_completed_stages_are_listed(self, repo, night):
        night()

        result = assemble(repo)

        assert len(result.nights[0].completed) == 3

    def test_skipped_and_failed_are_distinguishable(self, repo, night):
        """A morning that collapses both into "did not run" has thrown away the
        half that says whether anything is wrong."""
        night()

        statuses = {s.stage: s.status for s in assemble(repo).nights[0].stages}

        assert statuses["research"] == "skipped"
        assert statuses["build"] == "failed"

    def test_a_failed_stage_carries_the_reason_from_the_ledger(self, repo, night):
        """`run_stages` has no reason column, so this is recovered from
        `failures` by the scope embedded in its signature."""
        from secondshift.telemetry.failures import FailureType, signature

        run = night()
        exc = RuntimeError("the builder blew up")
        repo.insert_failure(
            failure_type=str(FailureType.ORCHESTRATOR_CRASH),
            signature=signature(FailureType.ORCHESTRATOR_CRASH, exc, scope="night.build"),
            message=str(exc),
            run_id=run,
        )

        reasons = briefing_module._failure_reasons(repo, run)

        assert reasons.get("build") == "the builder blew up"

    def test_the_reason_reaches_the_briefing(self, repo, night):
        from secondshift.telemetry.failures import FailureType, signature

        run = night()
        exc = RuntimeError("the builder blew up")
        repo.insert_failure(
            failure_type=str(FailureType.ORCHESTRATOR_CRASH),
            signature=signature(FailureType.ORCHESTRATOR_CRASH, exc, scope="night.build"),
            message=str(exc),
            run_id=run,
        )

        stages = {s.stage: s for s in assemble(repo).nights[0].stages}

        assert stages["build"].reason == "the builder blew up"
        # And a skipped stage has none, because nothing persists a skip reason.
        assert stages["research"].reason is None

    def test_the_briefing_survives_an_interviewer_that_cannot_run(
        self, repo, recorder, night, roster, entry
    ):
        """Principle 3 structurally: the facts are assembled with no model call,
        so a failing interviewer costs the questions and not the morning."""
        night()
        agents, prompts = roster
        broken = InterviewerStub(recorder, raises=RuntimeError("model down"))

        facts = assemble(repo)
        with pytest.raises(RuntimeError):
            raise_questions(
                repo,
                recorder,
                broken,
                facts,
                agent_id=agents["interviewer"],
                prompt_path=prompts["interviewer"],
                entry_id=entry,
                policy="cloud-assisted",
            )

        assert len(assemble(repo).nights) == 1
        assert assemble(repo).questions == ()


# -- the interviewer -------------------------------------------------------


class TestRaisingQuestions:
    QUESTIONS = (
        "Q: Do you read the digest on a phone?\n"
        "Why: The builder had two shapes and could not choose without knowing.\n\n"
        "Q: Should the critique rank by usefulness or by novelty?\n"
        "Why: Both are defensible and the ranking is recorded.\n"
    )

    def test_it_stores_each_question_with_its_rationale(
        self, repo, recorder, night, roster, entry
    ):
        night()
        agents, prompts = roster
        raised = raise_questions(
            repo,
            recorder,
            InterviewerStub(recorder, text=self.QUESTIONS),
            assemble(repo),
            agent_id=agents["interviewer"],
            prompt_path=prompts["interviewer"],
            entry_id=entry,
            policy="cloud-assisted",
        )

        assert len(raised) == 2
        rows = list(repo.connection.execute("SELECT * FROM decisions"))
        assert all(r["rationale"] for r in rows)

    def test_each_decision_names_the_invocation_that_raised_it(
        self, repo, recorder, night, roster, entry
    ):
        """So a prompt change is visible in the record rather than inferred."""
        night()
        agents, prompts = roster
        raise_questions(
            repo,
            recorder,
            InterviewerStub(recorder, text=self.QUESTIONS),
            assemble(repo),
            agent_id=agents["interviewer"],
            prompt_path=prompts["interviewer"],
            entry_id=entry,
            policy="cloud-assisted",
        )

        rows = list(repo.connection.execute("SELECT * FROM decisions"))
        assert all(r["raised_by_invocation_id"] for r in rows)

    def test_a_question_without_a_rationale_is_discarded(self):
        """A question without one is a quiz, and storing half of it would lose
        the distinction permanently."""
        assert parse_questions("Q: Why did you do that?\n") == []

    def test_a_rationale_without_a_question_is_discarded(self):
        assert parse_questions("Why: because of a thing\n") == []

    def test_the_interviewer_is_not_handed_the_raw_entry_text(
        self, repo, recorder, night, roster, entry
    ):
        """Its job is "what got stuck", a property of the run. Not passing the
        idea means a cloud-assisted interview does not put the original in
        front of a remote model a second time."""
        night()
        agents, prompts = roster
        stub = InterviewerStub(recorder, text=self.QUESTIONS)

        raise_questions(
            repo,
            recorder,
            stub,
            assemble(repo),
            agent_id=agents["interviewer"],
            prompt_path=prompts["interviewer"],
            entry_id=entry,
            policy="cloud-assisted",
        )

        sent = "\n".join(m.content for m in stub.messages)
        assert "weekly digest of my voice notes" not in sent

    def test_the_facts_carry_stage_outcomes(self, repo, night):
        night()

        facts = facts_for(assemble(repo).nights)

        assert "brief: complete" in facts
        assert "build: failed" in facts


# -- answering -------------------------------------------------------------


class TestAnswering:
    @pytest.fixture
    def decision(self, repo, entry):
        return repo.insert_decision(
            entry_id=entry,
            question="Do you read it on a phone?",
            rationale="two shapes, could not choose",
            status="open",
        )

    def test_answering_records_the_modality(self, repo, decision):
        answer(repo, decision, text="yes, phone", status="decided")

        row = repo.connection.execute(
            "SELECT * FROM decisions WHERE id = ?", (decision,)
        ).fetchone()
        assert row["answer_modality"] == "text"
        assert row["answer"] == "yes, phone"

    def test_answering_an_unknown_question_is_refused(self, repo):
        """There is no path that accepts an instruction. An answer is always to
        a question the system asked."""
        with pytest.raises(ValueError, match="unknown or already answered"):
            answer(repo, "no-such-decision", text="whatever", status="decided")

    def test_answering_twice_is_refused(self, repo, decision):
        answer(repo, decision, text="first", status="decided")

        with pytest.raises(ValueError):
            answer(repo, decision, text="second", status="decided")

    def test_queued_for_tonight_is_readable_as_pending_input(self, repo, decision):
        answer(repo, decision, text="try the phone shape", status="queued-for-tonight")

        pending = queued_for_tonight(repo)

        assert [r["id"] for r in pending] == [decision]

    def test_a_consumed_answer_names_the_run_that_took_it(
        self, repo, decision, run_id
    ):
        answer(repo, decision, text="try it", status="queued-for-tonight")

        mark_consumed(repo, decision, run_id)

        assert queued_for_tonight(repo) == []
        row = repo.connection.execute(
            "SELECT * FROM decisions WHERE id = ?", (decision,)
        ).fetchone()
        assert row["consumed_by_run_id"] == run_id

    def test_consuming_twice_is_refused(self, repo, decision, run_id):
        answer(repo, decision, text="try it", status="queued-for-tonight")
        mark_consumed(repo, decision, run_id)

        with pytest.raises(ValueError, match="already consumed"):
            mark_consumed(repo, decision, run_id)

    def test_deferred_and_obsolete_are_retained_not_deleted(self, repo, entry):
        for status in ("deferred", "obsolete"):
            d = repo.insert_decision(
                entry_id=entry, question="q", rationale="r", status="open"
            )
            answer(repo, d, text="later", status=status)

        rows = list(repo.connection.execute("SELECT status FROM decisions"))
        assert {r["status"] for r in rows} == {"deferred", "obsolete"}


# -- the airlock -----------------------------------------------------------


class TestWideningIsAnAttributableDecision:
    def test_an_authorized_widening_records_its_source(self, repo, entry):
        decision = repo.insert_decision(
            entry_id=entry,
            question="May I take this one to the cloud?",
            rationale="the local model cannot do the synthesis",
            status="open",
        )
        answer(repo, decision, text="yes", status="decided")

        resolution = resolve_policy(
            "local-only", available=True, upgrade_decision_id=decision
        )

        assert resolution.effective_policy is Policy.CLOUD_ASSISTED
        assert resolution.policy_source is PolicySource.DECISION_UPGRADE

    def test_widening_without_a_decision_is_refused(self):
        """Assert the negative. A flag that widened without attribution is the
        exact shape principle 2 names."""
        resolution = resolve_policy("local-only", available=True)

        assert resolution.effective_policy is Policy.LOCAL_ONLY
        assert resolution.policy_source is PolicySource.ENTRY_DEFAULT


# -- the scope boundary ----------------------------------------------------


class TestTheScopeBoundary:
    def test_an_empty_database_produces_no_questions(self, repo):
        """Every question comes from a `decisions` row.

        A module carrying its own question text would be a screen that works
        against an empty database and lies about it — which is what the "never
        ship hardcoded questions standing in for `decisions`" rule is about.
        Asserted behaviorally: an earlier version of this test grepped the
        source for a question mark and was matching SQL `?` placeholders, which
        would have passed forever whatever the module did.
        """
        result = assemble(repo)

        assert result.questions == ()
        assert result.is_empty

    def test_questions_come_from_rows_and_only_from_rows(self, repo, entry):
        """Add one row, get exactly one question, carrying that row's text."""
        repo.insert_decision(
            entry_id=entry,
            question="Do you read it on a phone?",
            rationale="two shapes",
            status="open",
        )

        result = assemble(repo)

        assert [q.question for q in result.questions] == ["Do you read it on a phone?"]

    def test_an_answered_question_is_not_asked_again(self, repo, entry):
        decision = repo.insert_decision(
            entry_id=entry, question="q", rationale="r", status="open"
        )
        answer(repo, decision, text="a", status="decided")

        assert assemble(repo).questions == ()

    def test_the_answer_surface_takes_a_decision_id(self):
        """`NOT_BUILDING.md` excludes a general chat interface by name. The
        guard is that no function here accepts free text without a question to
        attach it to."""
        import inspect

        from secondshift.morning.interview import answer as answer_fn

        parameters = list(inspect.signature(answer_fn).parameters)
        assert parameters[1] == "decision_id"

    def test_there_is_no_free_text_routing_function(self):
        from secondshift.morning import interview

        suspicious = [
            n
            for n in dir(interview)
            if n.startswith(("chat", "message", "ask_anything", "handle_input"))
        ]
        assert suspicious == []


class TestAPlaceholderIsNotAQuestion:
    """Found by running the real command and reading what landed: the `cloud`
    profile's `EchoReasoner` returns its own input, so the format instruction
    came back verbatim and `<the question>` was stored as something to ask a
    person over coffee. Green tests said nothing about it."""

    def test_an_echoed_template_raises_no_question(self):
        from secondshift.morning.interview import FORMAT_INSTRUCTION

        assert parse_questions(FORMAT_INSTRUCTION) == []

    def test_a_placeholder_in_the_question_is_discarded(self):
        assert parse_questions("Q: <the question>\nWhy: because\n") == []

    def test_a_placeholder_in_the_rationale_is_discarded(self):
        assert parse_questions("Q: Which shape?\nWhy: <what you tried>\n") == []

    def test_a_real_question_still_gets_through(self):
        assert parse_questions(
            "Q: Do you read it on a phone?\nWhy: two shapes, could not choose\n"
        ) == [("Do you read it on a phone?", "two shapes, could not choose")]
