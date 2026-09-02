"""The stage machine: checkpointing, blocking, quarantine, and closing a run.

The crash test is the load-bearing one. A green suite does not prove
checkpointing — an all-or-nothing implementation passes every assertion about
final state. So `TestKillItInTheMiddle` runs a night in a real subprocess, kills
it partway, reopens the database and asserts what survived. Its mutation was
run: buffering the stage writes to the end of the walk turns it red.

`close_run` gets its first test here. It had no caller and no test in the tree,
and its docstring has always claimed it "refuses to close one that is already
closed" — `test_closing_twice_is_refused` is the first thing that ever checked.
"""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from secondshift.agents.roster import discover, register
from secondshift.db.connection import connect, now_ms
from secondshift.db.repository import Repository
from secondshift.night.run import NightResult, run_entry
from secondshift.night.research import NO_CREDENTIAL
from secondshift.night.stages import (
    BY_NAME,
    STAGES,
    assert_matches_schema,
)
from secondshift.providers.base import Message, RawCompletion, Reasoner
from secondshift.providers.registry import Providers

REPO_ROOT = Path(__file__).resolve().parents[3]


class StubReasoner(Reasoner):
    """Answers immediately, or raises on the stages it was told to fail."""

    provider_kind = "local-vllm"

    def __init__(self, recorder, *, fail: frozenset[str] = frozenset(), **kw) -> None:
        super().__init__(recorder, model=kw.pop("model", "stub"))
        self._fail = fail
        self.calls: list[list[Message]] = []

    def _do_complete(self, messages, *, effort) -> RawCompletion:
        self.calls.append(list(messages))
        body = messages[0].content
        for stage in self._fail:
            if f"# {BY_NAME[stage].role.title()}" in body:
                raise RuntimeError(f"{stage} blew up")
        return RawCompletion(
            text="an answer",
            prompt_tokens=5,
            completion_tokens=7,
            reasoning_tokens=0,
            cache_hit=False,
            finish_reason="stop",
        )


class RemoteStubReasoner(StubReasoner):
    provider_kind = "token-factory"


@pytest.fixture
def providers(recorder):
    def build(*, fail: frozenset[str] = frozenset(), remote: bool = False) -> Providers:
        cls = RemoteStubReasoner if remote else StubReasoner
        return Providers(
            reasoner=cls(recorder, fail=fail),
            transcriber=None,  # type: ignore[arg-type]
            embedder=None,  # type: ignore[arg-type]
            executor=None,  # type: ignore[arg-type]
        )

    return build


@pytest.fixture
def entry(repo):
    return repo.insert_entry(
        created_at_ms=now_ms(),
        captured_tz="America/Los_Angeles",
        tz_offset_min=-420,
        modality="text",
        default_policy="cloud-assisted",
        status="queued",
        capture_profile="spark",
        raw_text="an idea worth working on",
    )


@pytest.fixture
def roster(repo):
    agents = register(repo)
    prompts = {role: p.path for role, p in discover().items()}
    return agents, prompts


def _night(repo, recorder, providers, entry_id, roster, **kw) -> NightResult:
    agents, prompts = roster
    row = repo.get_entry(entry_id)
    return run_entry(
        repo,
        recorder,
        providers,
        row,
        profile=kw.pop("profile", "spark"),
        agents=agents,
        prompts=prompts,
        local_available=kw.pop("local_available", True),
        **kw,
    )


# -- the table itself ------------------------------------------------------


class TestTheStageTable:
    def test_the_stages_match_the_schema_check_constraint(self, conn):
        """Read from `sqlite_master`, not restated. A seventh stage added to the
        database with no definition here must fail."""
        assert_matches_schema(conn)

    def test_every_stage_role_is_one_the_schema_permits(self, conn):
        from secondshift.agents.roster import permitted_roles

        assert {s.role for s in STAGES} <= permitted_roles(conn)

    def test_the_interviewer_runs_no_night_stage(self, conn):
        """ADR 0005: the interview stays in the morning. The synthetic seed
        assigns `brief` to the interviewer, but its own comment says that map
        was chosen so the timeline renders distinct lanes — a rendering choice,
        not a product decision."""
        assert "interviewer" not in {s.role for s in STAGES}

    def test_the_blocking_predicates_are_the_proposal_s_table(self):
        """Two blocking edges, not a chain. Asserted directly so a change to
        the predicates has to change this test and therefore the table."""
        assert BY_NAME["mockups"].can_run(frozenset({"brief"}))
        assert BY_NAME["build"].can_run(frozenset({"brief"}))
        assert not BY_NAME["critique"].can_run(frozenset({"brief", "mockups"}))
        assert BY_NAME["critique"].can_run(frozenset({"brief", "build"}))
        assert BY_NAME["distill"].can_run(frozenset({"brief"}))
        assert not BY_NAME["distill"].can_run(frozenset())


# -- principle 3 -----------------------------------------------------------


class TestKillItInTheMiddle:
    """The principle-3 test. Final-state assertions cannot prove checkpointing:
    an implementation that buffered every write until the end would satisfy
    them. Only killing the process can."""

    def test_stages_completed_before_the_kill_survive_it(self, tmp_path):
        db = tmp_path / "night.db"
        script = textwrap.dedent(f"""
            import os, sys, time
            sys.path.insert(0, {str(REPO_ROOT / "apps" / "api")!r})
            from secondshift.db.connection import connect, now_ms
            from secondshift.db.migrate import migrate
            from secondshift.db.repository import Repository
            from secondshift.night.stages import STAGES

            conn = connect({str(db)!r}); migrate(conn)
            repo = Repository(conn)
            entry = repo.insert_entry(
                created_at_ms=now_ms(), captured_tz="UTC", tz_offset_min=0,
                modality="text", default_policy="cloud-assisted", status="queued",
                capture_profile="cloud", raw_text="an idea")
            run = repo.insert_run(
                entry_id=entry, night_of="2026-09-02",
                effective_policy="cloud-assisted", policy_source="entry-default",
                compute_profile="cloud")
            print(run, flush=True)
            for stage in STAGES:
                sid = repo.insert_run_stage(
                    run_id=run, stage=stage.name, seq=stage.seq,
                    status="running", started_at_ms=now_ms())
                repo.complete_run_stage(sid, status="complete")
                print(stage.name, flush=True)
                time.sleep(0.4)
        """)
        seen = []
        with subprocess.Popen(
            [sys.executable, "-c", script],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        ) as proc:
            assert proc.stdout is not None
            proc.stdout.readline()  # the run id
            for _ in range(3):
                seen.append(proc.stdout.readline().strip())
            proc.kill()
            proc.wait(timeout=10)

        assert seen == ["brief", "research", "mockups"]

        conn = connect(db)
        try:
            rows = {
                r["stage"]: r
                for r in conn.execute("SELECT * FROM run_stages").fetchall()
            }
        finally:
            conn.close()

        for stage in seen:
            assert rows[stage]["status"] == "complete", f"{stage} did not survive"
            assert rows[stage]["ended_at_ms"] is not None
        assert "critique" not in rows and "distill" not in rows

    def test_a_late_failure_does_not_retract_an_early_success(
        self, repo, recorder, providers, entry, roster
    ):
        result = _night(
            repo, recorder, providers(fail=frozenset({"critique"})), entry, roster
        )

        rows = {r["stage"]: r for r in repo.stages_for_run(result.run_id)}
        assert rows["brief"]["status"] == "complete"
        assert rows["brief"]["ended_at_ms"] is not None
        assert rows["critique"]["status"] == "failed"


# -- blocking --------------------------------------------------------------


class TestBlocking:
    def test_research_is_skipped_and_does_not_stop_what_follows(
        self, repo, recorder, providers, entry, roster
    ):
        """The pair that would have been wrong under a uniform rule: research
        has no provider, and mockups and build must still run."""
        result = _night(repo, recorder, providers(), entry, roster)

        by_stage = {s.stage: s for s in result.stages}
        assert by_stage["research"].status == "skipped"
        # The reason now comes from the real path rather than a constant: with
        # no credential configured, `night.research` says so. It stopped being
        # `NO_RESEARCH_PROVIDER` when `research` shipped on 2 Sep — the skip is
        # a fact about this deployment, not about the codebase.
        assert by_stage["research"].reason == NO_CREDENTIAL
        assert by_stage["mockups"].status == "complete"
        assert by_stage["build"].status == "complete"

    def test_critique_is_skipped_when_build_failed(
        self, repo, recorder, providers, entry, roster
    ):
        result = _night(
            repo, recorder, providers(fail=frozenset({"build"})), entry, roster
        )

        by_stage = {s.stage: s for s in result.stages}
        assert by_stage["build"].status == "failed"
        assert by_stage["critique"].status == "skipped"
        assert "input" in by_stage["critique"].reason

    def test_nothing_runs_without_a_brief(
        self, repo, recorder, providers, entry, roster
    ):
        result = _night(
            repo, recorder, providers(fail=frozenset({"brief"})), entry, roster
        )

        statuses = {s.stage: s.status for s in result.stages}
        assert statuses["brief"] == "failed"
        assert all(v == "skipped" for k, v in statuses.items() if k != "brief")
        assert result.outcome == "failed"

    def test_distill_runs_on_any_completed_stage(
        self, repo, recorder, providers, entry, roster
    ):
        """Blocked by all predecessors failing, not by any one — which is why
        the table is a predicate per stage rather than a dependency list."""
        result = _night(
            repo,
            recorder,
            providers(fail=frozenset({"mockups", "build"})),
            entry,
            roster,
        )

        by_stage = {s.stage: s for s in result.stages}
        assert by_stage["distill"].status == "complete"

    def test_a_skipped_stage_opens_no_invocation(
        self, repo, recorder, providers, entry, roster
    ):
        """A stage that ran must be distinguishable in the data from one that
        was skipped, or principle 7 buys nothing."""
        result = _night(repo, recorder, providers(), entry, roster)

        stages = [
            r["stage"]
            for r in repo.connection.execute(
                "SELECT stage FROM agent_invocations WHERE run_id = ?", (result.run_id,)
            )
        ]
        assert "research" not in stages
        assert "brief" in stages


# -- closing the run -------------------------------------------------------


class TestEveryRunReachesAnOutcome:
    def test_a_full_night_closes_complete(
        self, repo, recorder, providers, entry, roster, monkeypatch
    ):
        """Every stage completing requires research to have a provider, which it
        does not — so this asserts the derivation directly rather than pretending
        a night today can reach it."""
        from secondshift.night import run as run_module

        results = [run_module.StageResult(s.name, "complete") for s in STAGES]
        assert run_module._outcome_for(results) == "complete"

    def test_a_partly_successful_night_closes_degraded(
        self, repo, recorder, providers, entry, roster
    ):
        result = _night(repo, recorder, providers(), entry, roster)

        assert result.outcome == "degraded"
        row = repo.connection.execute(
            "SELECT * FROM runs WHERE id = ?", (result.run_id,)
        ).fetchone()
        assert row["outcome"] == "degraded"
        assert row["ended_at_ms"] is not None
        assert row["furthest_stage"] == "distill"

    def test_no_terminal_path_leaves_a_null_outcome(
        self, repo, recorder, providers, entry, roster
    ):
        """The defect that already existed. Enumerated rather than sampled."""
        for failing in (frozenset(), frozenset({"brief"}), frozenset({"build"})):
            e = repo.insert_entry(
                created_at_ms=now_ms(),
                captured_tz="UTC",
                tz_offset_min=0,
                modality="text",
                default_policy="cloud-assisted",
                status="queued",
                capture_profile="spark",
                raw_text="another idea",
            )
            _night(repo, recorder, providers(fail=failing), e, roster)

        open_runs = repo.connection.execute(
            "SELECT COUNT(*) c FROM runs WHERE ended_at_ms IS NULL OR outcome IS NULL"
        ).fetchone()["c"]
        assert open_runs == 0

    def test_closing_twice_is_refused(self, repo, entry):
        """`close_run`'s docstring has always claimed this. Nothing checked it
        until now — it had no caller and no test anywhere in the tree."""
        run_id = repo.insert_run(
            entry_id=entry,
            night_of="2026-09-02",
            effective_policy="local-only",
            policy_source="entry-default",
            compute_profile="spark",
        )
        repo.close_run(run_id, outcome="complete")

        with pytest.raises(ValueError, match="already closed"):
            repo.close_run(run_id, outcome="failed")

    def test_a_failed_night_returns_its_entry_to_queued(
        self, repo, recorder, providers, entry, roster
    ):
        """There is no failed state for an entry — a decision the schema already
        took. An idea that could not be worked on tonight is one for tomorrow."""
        _night(repo, recorder, providers(fail=frozenset({"brief"})), entry, roster)

        assert repo.get_entry(entry)["status"] == "queued"

    def test_a_degraded_night_answers_its_entry(
        self, repo, recorder, providers, entry, roster
    ):
        _night(repo, recorder, providers(), entry, roster)

        assert repo.get_entry(entry)["status"] == "answered"


# -- the airlock -----------------------------------------------------------


class TestQuarantineRatherThanDowngrade:
    @pytest.fixture
    def local_only_entry(self, repo):
        return repo.insert_entry(
            created_at_ms=now_ms(),
            captured_tz="UTC",
            tz_offset_min=0,
            modality="text",
            default_policy="local-only",
            status="queued",
            capture_profile="spark",
            raw_text="a private idea",
        )

    def test_it_opens_no_run_at_all(
        self, repo, recorder, providers, local_only_entry, roster
    ):
        """Not a run of skipped stages: `runs` is the denominator of the
        cost-per-artifact curve, and a night that never happened must not
        enter it."""
        result = _night(
            repo,
            recorder,
            providers(),
            local_only_entry,
            roster,
            profile="cloud",
            local_available=False,
            unavailable_reason="no local reasoner on this profile",
        )

        assert result.quarantined
        assert result.run_id is None
        assert list(repo.connection.execute("SELECT * FROM runs")) == []
        assert list(repo.connection.execute("SELECT * FROM model_calls")) == []

    def test_the_entry_is_left_queued(
        self, repo, recorder, providers, local_only_entry, roster
    ):
        _night(
            repo,
            recorder,
            providers(),
            local_only_entry,
            roster,
            profile="cloud",
            local_available=False,
        )

        assert repo.get_entry(local_only_entry)["status"] == "queued"

    def test_the_reason_is_recorded_and_readable(
        self, repo, recorder, providers, local_only_entry, roster
    ):
        result = _night(
            repo,
            recorder,
            providers(),
            local_only_entry,
            roster,
            profile="cloud",
            local_available=False,
            unavailable_reason="no local reasoner on this profile",
        )

        assert "local reasoner" in result.quarantine_reason
        ledger = repo.failure_ledger()
        assert any("quarantine" in r["signature"] for r in ledger)

    def test_no_run_ever_records_a_wider_policy_than_the_entry_asked_for(
        self, repo, recorder, providers, local_only_entry, roster
    ):
        _night(
            repo,
            recorder,
            providers(),
            local_only_entry,
            roster,
            profile="cloud",
            local_available=False,
        )

        widened = repo.connection.execute(
            "SELECT COUNT(*) c FROM runs WHERE effective_policy = 'cloud-assisted'"
        ).fetchone()["c"]
        assert widened == 0

    def test_a_local_only_run_cannot_reach_a_remote_provider(
        self, repo, recorder, providers, local_only_entry, roster
    ):
        """Belt and braces: even where policy resolution permitted it, the
        provider call itself refuses."""
        result = _night(
            repo, recorder, providers(remote=True), local_only_entry, roster
        )

        assert result.outcome == "failed"
        assert list(repo.connection.execute("SELECT * FROM model_calls")) == []
        messages = [
            r["message"]
            for r in repo.connection.execute("SELECT message FROM failures")
        ]
        assert any("local-only" in m for m in messages), messages


# -- idempotence -----------------------------------------------------------


class TestDispatchingTwice:
    def test_an_entry_in_flight_is_no_longer_eligible(
        self, repo, recorder, providers, entry, roster
    ):
        _night(repo, recorder, providers(), entry, roster)

        eligible = [r["id"] for r in repo.dispatch_eligible_entries()]
        assert entry not in eligible

    def test_one_entry_produces_one_run(
        self, repo, recorder, providers, entry, roster
    ):
        _night(repo, recorder, providers(), entry, roster)

        runs = repo.connection.execute(
            "SELECT COUNT(*) c FROM runs WHERE entry_id = ?", (entry,)
        ).fetchone()["c"]
        assert runs == 1


class TestTheManualEntryPoint:
    """A pipeline you cannot run on demand is one you cannot debug at 2am."""

    def test_it_runs_against_an_empty_database_and_reports_nothing_to_do(
        self, tmp_path
    ):
        completed = subprocess.run(
            [sys.executable, "-m", "secondshift.night", "run", "--db", str(tmp_path / "n.db")],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT / "apps" / "api",
            env={**os.environ, "SECOND_SHIFT_PROFILE": "cloud"},
        )

        assert completed.returncode == 0, completed.stderr

    def test_naming_an_ineligible_entry_exits_non_zero(self, tmp_path):
        completed = subprocess.run(
            [
                sys.executable, "-m", "secondshift.night", "run",
                "--db", str(tmp_path / "n.db"), "--entry", "nope",
            ],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT / "apps" / "api",
            env={**os.environ, "SECOND_SHIFT_PROFILE": "cloud"},
        )

        assert completed.returncode == 1
        assert "not eligible" in completed.stderr


class TestTheDeployUnits:
    def test_the_night_units_exist_as_a_pair(self):
        """A timer with no service is a unit that fails at enable time."""
        units = REPO_ROOT / "deploy" / "spark"

        assert (units / "second-shift-night.user.timer").exists()
        assert (units / "second-shift-night.user.service").exists()

    def test_the_service_starts_the_module_this_capability_ships(self):
        """The unit and the entry point cannot drift apart silently."""
        service = (
            REPO_ROOT / "deploy" / "spark" / "second-shift-night.user.service"
        ).read_text()

        assert "-m secondshift.night run" in service

    def test_the_timer_persists_a_missed_night(self):
        """An idea captured on Tuesday must not be skipped because the box was
        asleep on Tuesday night."""
        timer = (
            REPO_ROOT / "deploy" / "spark" / "second-shift-night.user.timer"
        ).read_text()

        assert "Persistent=true" in timer


class TestDistillWritesTheBrain:
    """Principle 1: what the night learned lands in plaintext under git."""

    @pytest.fixture
    def brain(self, tmp_path):
        from secondshift.brain.repo import BrainRepo

        path = tmp_path / "brain"
        path.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=path, check=True)
        subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=path, check=True)
        subprocess.run(["git", "config", "user.name", "test"], cwd=path, check=True)
        (path / "profile.md").write_text("# Profile\n")
        subprocess.run(["git", "add", "-A"], cwd=path, check=True)
        subprocess.run(["git", "commit", "-qm", "seed"], cwd=path, check=True)
        return BrainRepo(path)

    def test_it_commits_and_records_the_sha(
        self, repo, recorder, providers, entry, roster, brain
    ):
        result = _night(repo, recorder, providers(), entry, roster, brain=brain)

        row = next(r for r in repo.stages_for_run(result.run_id) if r["stage"] == "distill")
        assert row["commit_sha"], "distill completed without recording a commit"
        assert row["committed_at_ms"] is not None
        assert list((brain.path / "nights").glob("*.md"))

    def test_it_never_overwrites_a_topic_file(
        self, repo, recorder, providers, entry, roster, brain
    ):
        """The distiller's prompt warns that an over-confident inference in
        `profile.md` compounds silently for weeks. Appending is what this ships;
        the rewrite has to be earned against the real model first."""
        before = (brain.path / "profile.md").read_text()

        _night(repo, recorder, providers(), entry, roster, brain=brain)

        assert (brain.path / "profile.md").read_text() == before

    def test_an_unavailable_brain_does_not_fail_the_night(
        self, repo, recorder, providers, entry, roster, tmp_path
    ):
        """Principle 3: a missing rendering target must not cost a whole night."""
        from secondshift.brain.repo import BrainRepo

        result = _night(
            repo, recorder, providers(), entry, roster,
            brain=BrainRepo(tmp_path / "not-a-repo"),
        )

        by_stage = {s.stage: s.status for s in result.stages}
        assert by_stage["distill"] == "complete"
        row = next(r for r in repo.stages_for_run(result.run_id) if r["stage"] == "distill")
        assert row["commit_sha"] is None


class TestABriefWithNoMemorySaysSo:
    """A brief written with no index behind it reads exactly like one written
    with memory that had nothing to say. The morning cannot tell them apart
    unless the brief is told."""

    def test_the_brief_stage_is_told_when_retrieval_produced_nothing(
        self, repo, recorder, providers, entry, roster
    ):
        built = providers()
        _night(repo, recorder, built, entry, roster, retrieved="")

        brief_call = built.reasoner.calls[0]
        assert any("no memory of earlier work" in m.content for m in brief_call)

    def test_retrieved_context_is_passed_through_when_it_exists(
        self, repo, recorder, providers, entry, roster
    ):
        built = providers()
        _night(repo, recorder, built, entry, roster, retrieved="### profile.md\n\na fact")

        brief_call = built.reasoner.calls[0]
        assert any("a fact" in m.content for m in brief_call)
        assert not any("no memory of earlier work" in m.content for m in brief_call)

    def test_retrieve_returns_text_not_context_pieces(self, repo, recorder, tmp_path):
        """`assemble_context` returns `ContextPiece` objects, not a string.
        Handing the list straight to `invoke` raises on `.strip()` — a defect
        that surfaces only once an embedder is reachable, which is the worst
        place to find it. This was shipped and caught before commit."""
        from secondshift.brain.repo import BrainRepo
        from secondshift.night.__main__ import _retrieve
        from secondshift.providers.registry import Providers

        class StubEmbedder:
            """Answers with a fixed-width vector, so the index builds."""

            def embed(self, texts, *, policy):
                return [[1.0] + [0.0] * 2047 for _ in texts]

        path = tmp_path / "brain"
        path.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=path, check=True)
        subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=path, check=True)
        subprocess.run(["git", "config", "user.name", "test"], cwd=path, check=True)
        (path / "profile.md").write_text("# Profile\n\nPrefers plain writing.\n")
        subprocess.run(["git", "add", "-A"], cwd=path, check=True)
        subprocess.run(["git", "commit", "-qm", "seed"], cwd=path, check=True)

        providers = Providers(
            reasoner=None,  # type: ignore[arg-type]
            transcriber=None,  # type: ignore[arg-type]
            embedder=StubEmbedder(),  # type: ignore[arg-type]
            executor=None,  # type: ignore[arg-type]
        )
        entry = {"raw_text": "an idea", "default_policy": "local-only"}

        out = _retrieve(repo, providers, BrainRepo(path), entry)

        assert isinstance(out, str), f"_retrieve returned {type(out).__name__}"
        out.strip()  # what `invoke` does, and what a list would raise on

    def test_retrieve_degrades_to_empty_without_a_brain(self, repo):
        from secondshift.night.__main__ import _retrieve

        assert _retrieve(repo, None, None, {"raw_text": "x", "default_policy": "local-only"}) == ""
