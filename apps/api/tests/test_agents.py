"""The roster, its pinning, and one recorded invocation.

`prompt_sha` is the load-bearing part. It exists so an eight-week curve can be
shown to measure the brain rather than a prompt edited on day 40, and until this
capability the only thing writing it was a fixture writing `deadbeef` against a
path that never existed. The pinning tests here are written to go red when the
hash stops being derived from the file: replacing `sha256_of`'s body with a
constant turns four of them red, including the append-only guard, because a
constant hash makes an edit in place undetectable. That mutation was run.

There is deliberately no test here that asserts a hardcoded constant differs
from a real hash. One was written and deleted: it was true whatever the
implementation did, which makes it exactly the decoration this file exists to
prevent.
"""

from __future__ import annotations

import hashlib

import pytest

from secondshift.agents import roster
from secondshift.agents.invoke import AgentTurn, invoke, strip_reasoning
from secondshift.agents.roster import (
    PromptEditedInPlace,
    PromptFileMissing,
    discover,
    permitted_roles,
    register,
)
from secondshift.airlock.policy import AirlockViolation
from secondshift.providers.base import Message, RawCompletion, Reasoner

ROLES = {"interviewer", "researcher", "architect", "builder", "critic", "distiller"}


class StubReasoner(Reasoner):
    """A local reasoner that answers with whatever it was told to answer."""

    provider_kind = "local-vllm"

    def __init__(self, recorder, *, text: str = "an answer", **kw) -> None:
        super().__init__(recorder, model=kw.pop("model", "stub"))
        self._text = text
        self.messages: list[Message] = []

    def _do_complete(self, messages, *, effort) -> RawCompletion:
        self.messages = list(messages)
        return RawCompletion(
            text=self._text,
            prompt_tokens=5,
            completion_tokens=7,
            reasoning_tokens=0,
            cache_hit=False,
            finish_reason="stop",
        )


class RemoteStubReasoner(StubReasoner):
    provider_kind = "token-factory"


@pytest.fixture
def prompts(tmp_path):
    """A prompt directory under the test's control, not the shipped one."""
    d = tmp_path / "prompts"
    d.mkdir()
    for role in sorted(ROLES):
        (d / f"{role}.v1.md").write_text(f"# {role}\n\nDraft.\n")
    return d


# -- the shipped roster ----------------------------------------------------


class TestTheShippedPrompts:
    def test_every_role_the_schema_permits_has_a_prompt(self, conn):
        """Enumerated from the CHECK constraint, not from a list in this file.

        A seventh role added to the database with no prompt behind it must fail
        here. It cannot, if the test carries its own copy of the six.
        """
        assert permitted_roles(conn) == set(discover())

    def test_the_permitted_roles_are_read_from_the_database(self, conn):
        assert permitted_roles(conn) == ROLES

    def test_each_shipped_prompt_says_it_is_a_draft(self):
        """What a prompt says is the subject's decision, not the author's."""
        for prompt in discover().values():
            assert "DRAFT" in prompt.path.read_text()

    def test_each_shipped_prompt_instructs_the_model_to_close_its_reasoning(self):
        """The live model emits `<think>` inline. A prompt that ignores that
        produces briefs opening with deliberation."""
        for prompt in discover().values():
            assert "</think>" in prompt.path.read_text()

    def test_a_malformed_filename_is_refused_rather_than_skipped(self, tmp_path):
        (tmp_path / "researcher.md").write_text("no version in the name")

        with pytest.raises(ValueError, match="is not <role>.v<n>.md"):
            discover(tmp_path)


# -- pinning ---------------------------------------------------------------


class TestPinningByContent:
    def test_the_recorded_sha_is_the_file_s_sha(self, repo, prompts):
        register(repo, directory=prompts)

        for role in ROLES:
            row = repo.get_agent(role, 1)
            expected = hashlib.sha256((prompts / f"{role}.v1.md").read_bytes()).hexdigest()
            assert row["prompt_sha"] == expected

    def test_editing_a_prompt_changes_its_hash(self, prompts):
        before = roster.sha256_of(prompts / "builder.v1.md")
        (prompts / "builder.v1.md").write_text("# builder\n\nDifferent.\n")

        assert roster.sha256_of(prompts / "builder.v1.md") != before

    def test_hashing_a_file_that_is_not_there_raises(self, tmp_path):
        with pytest.raises(PromptFileMissing, match="cannot be read"):
            roster.sha256_of(tmp_path / "absent.v1.md")

    def test_a_prompt_that_vanishes_between_listing_and_reading_writes_no_row(
        self, repo, prompts, monkeypatch
    ):
        """A row naming a file that is not there records unverifiable provenance.

        Listing and reading are two syscalls with a gap between them. The guard
        has to be on the read, not only on the listing, or the gap is where a
        row with no prompt behind it gets written.
        """
        phantom = roster.PromptFile("critic", 1, prompts / "gone.v1.md")
        monkeypatch.setattr(roster, "discover", lambda directory=None: {"critic": phantom})

        with pytest.raises(PromptFileMissing):
            register(repo, directory=prompts)

        assert repo.active_agents() == []


class TestPromptsAreAppendOnly:
    def test_an_edit_in_place_is_refused_naming_both_hashes(self, repo, prompts):
        """The same guard the rubric got, for the same reason.

        An edit in place silently redefines what every prior invocation was
        measuring, and the curve reads as settled while it is not.
        """
        register(repo, directory=prompts)
        (prompts / "architect.v1.md").write_text("# architect\n\nRewritten.\n")

        with pytest.raises(PromptEditedInPlace, match="append-only"):
            register(repo, directory=prompts)

    def test_a_superseding_version_registers_beside_the_old_one(self, repo, prompts):
        register(repo, directory=prompts)
        (prompts / "critic.v2.md").write_text("# critic\n\nThe subject's words.\n")

        register(repo, directory=prompts)

        assert repo.get_agent("critic", 1) is not None
        assert repo.get_agent("critic", 2) is not None

    def test_registering_twice_writes_nothing_the_second_time(self, repo, prompts):
        """Idempotent, which is what makes it safe to run at every startup."""
        first = register(repo, directory=prompts)
        before = len(repo.active_agents())

        second = register(repo, directory=prompts)

        assert first == second
        assert len(repo.active_agents()) == before


# -- invocation ------------------------------------------------------------


class TestInvokingAnAgent:
    def test_it_records_the_invocation_and_the_model_call(
        self, repo, recorder, prompts, run_id
    ):
        agents = register(repo, directory=prompts)
        reasoner = StubReasoner(recorder, text="a brief")

        turn = invoke(
            recorder,
            reasoner,
            role="researcher",
            agent_id=agents["researcher"],
            prompt_path=prompts / "researcher.v1.md",
            task="summarize this",
            policy="cloud-assisted",
            run_id=run_id,
        )

        assert turn.text == "a brief"
        invocations = list(
            repo.connection.execute("SELECT * FROM agent_invocations")
        )
        assert [r["run_id"] for r in invocations] == [run_id]
        calls = list(repo.connection.execute("SELECT * FROM model_calls"))
        assert [r["policy"] for r in calls] == ["cloud-assisted"]

    def test_the_prompt_file_is_the_system_message(self, repo, recorder, prompts, run_id):
        agents = register(repo, directory=prompts)
        reasoner = StubReasoner(recorder)

        invoke(
            recorder,
            reasoner,
            role="critic",
            agent_id=agents["critic"],
            prompt_path=prompts / "critic.v1.md",
            task="rank these",
            policy="local-only",
            run_id=run_id,
        )

        assert reasoner.messages[0].role == "system"
        assert reasoner.messages[0].content == (prompts / "critic.v1.md").read_text()

    def test_context_is_passed_through_not_retrieved(
        self, repo, recorder, prompts, run_id
    ):
        """An agent takes what it is handed and does no retrieval of its own."""
        agents = register(repo, directory=prompts)
        reasoner = StubReasoner(recorder)

        invoke(
            recorder,
            reasoner,
            role="architect",
            agent_id=agents["architect"],
            prompt_path=prompts / "architect.v1.md",
            task="plan it",
            policy="local-only",
            run_id=run_id,
            context="a retrieved fact",
        )

        assert any("a retrieved fact" in m.content for m in reasoner.messages)

    def test_a_local_only_invocation_cannot_reach_a_remote_provider(
        self, repo, recorder, prompts, run_id
    ):
        """Refused at the call, before the provider, and nothing recorded."""
        agents = register(repo, directory=prompts)
        remote = RemoteStubReasoner(recorder)

        with pytest.raises(AirlockViolation):
            invoke(
                recorder,
                remote,
                role="builder",
                agent_id=agents["builder"],
                prompt_path=prompts / "builder.v1.md",
                task="build it",
                policy="local-only",
                run_id=run_id,
            )

        assert list(repo.connection.execute("SELECT * FROM model_calls")) == []


class TestVisibleReasoning:
    def test_deliberation_before_the_close_is_dropped(self):
        raw = "<think>weighing it up</think>\n\nThe answer."
        assert strip_reasoning(raw) == "The answer."

    def test_text_without_the_delimiter_passes_through_whole(self):
        """A model that stops emitting it degrades to verbose, not to empty."""
        assert strip_reasoning("Just the answer.") == "Just the answer."

    def test_the_turn_reports_that_it_had_to_trim(self, recorder):
        """Worth surfacing: a brief that needed trimming is evidence about the
        prompt, and the prompt is what is being measured."""
        trimmed = AgentTurn("critic", "a", "The answer.", "<think>x</think>The answer.")
        untrimmed = AgentTurn("critic", "a", "The answer.", "The answer.")

        assert trimmed.showed_its_reasoning
        assert not untrimmed.showed_its_reasoning

    def test_only_the_last_close_counts(self):
        """A prompt that itself mentions the delimiter must not truncate wrongly."""
        raw = "<think>I should end with </think> as instructed</think>Final."
        assert strip_reasoning(raw) == "Final."


def test_the_agents_package_writes_no_telemetry_of_its_own():
    """The base classes own it. An agent that records is an agent that can
    record differently from every other caller."""
    from pathlib import Path

    package = Path(roster.__file__).parent
    for module in package.glob("*.py"):
        assert "record_" not in module.read_text(), module.name
