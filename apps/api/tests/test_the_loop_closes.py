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
        assert len(queued_for_tonight(repo)) == 1

        _run(repo, recorder, entry, roster, tmp_path)

        assert queued_for_tonight(repo) == []

    def test_an_answer_is_taken_once_not_every_night(
        self, repo, recorder, entry, roster, tmp_path
    ):
        """`mark_consumed` refuses a second claim, so an answer feeds one night
        and not every night after it.

        Tested across two entries rather than by re-queueing one: the schema
        permits `running -> answered` and `answered -> archived` and nothing
        else, so an entry the night worked can never return to `queued`. That
        is a real constraint and the test respects it rather than routing
        around it.
        """
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
