"""The measurement spine: sampling, pinning, and scoring against a recorded brain."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from secondshift.brain.repo import BrainRepo, BrainUnavailable
from secondshift.evals.__main__ import main
from secondshift.evals.content import Rubric, load_prompts, load_rubric, load_threshold
from secondshift.agents.invoke import invoke
from secondshift.agents.roster import discover, register
from secondshift.config import LocalReasonerSettings
from secondshift.evals.judge import (
    DIMENSIONS,
    Judgement,
    ModelJudge,
    StubJudge,
    UnreadableJudgement,
)
from secondshift.evals.runner import (
    AWAITING,
    IMPROVED,
    NO_IMPROVEMENT_SHOWN,
    REGRESSED,
    EvalRunner,
    NoJudgeConfigured,
    NotComparable,
    RubricMismatch,
    UNRECORDED,
)
from secondshift.providers.base import Completion
from secondshift.providers.vllm import VllmReasoner

GOOD = {d: 4 for d in DIMENSIONS}

#: Derived from this file's location, never hardcoded: an absolute developer
#: path fails on the target machine and leaks a home directory into a public
#: repository.
REPO_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def brain(tmp_path) -> BrainRepo:
    path = tmp_path / "brain"
    (path / "skills").mkdir(parents=True)
    (path / "profile.md").write_text("# Profile\n\nWeek one belief.\n")
    (path / "style-guide.md").write_text("# Style\n\nDirect.\n")
    for args in (
        ["init", "-q", "-b", "main"],
        ["config", "user.email", "t@example.invalid"],
        ["config", "user.name", "T"],
        ["add", "-A"],
        ["commit", "-q", "-m", "week one"],
    ):
        subprocess.run(["git", "-C", str(path), *args], check=True, capture_output=True)
    return BrainRepo(path)


@pytest.fixture
def rubric(tmp_path) -> Rubric:
    path = tmp_path / "rubric.md"
    path.write_text("# Rubric v1\n\nFive dimensions, one to five.\n")
    return load_rubric(path)


@pytest.fixture
def runner(repo, brain) -> EvalRunner:
    return EvalRunner(repo, brain=brain, samples=3)


def _seed_and_activate(runner, rubric, slugs=("a", "b")):
    from secondshift.evals.content import PromptCandidate

    runner.load_candidates(
        [PromptCandidate(slug=s, label=s, prompt=f"prompt {s}") for s in slugs], rubric
    )
    runner.activate(list(slugs))


#: The two generators that matter, as the pricing fixture knows them: the local
#: reasoner and the cloud one. The policy is part of the tuple because the
#: `model_calls` CHECK refuses a `local-only` row naming a remote provider, so a
#: pair that disagrees is rejected by the database rather than by a test.
LOCAL = ("local-vllm", "nemotron-3.5-lightning-30b", "local-only")
CLOUD = ("token-factory", "nemotron-3-super", "cloud-assisted")


def _generator(recorder, source=LOCAL):
    """A `generate` callable that records its call, the way a provider does.

    It returns the recorded completion rather than text because that is the
    contract: the result row names the call that produced it, and the foreign
    key means a fabricated id would be rejected. So the call is real here, which
    also makes the generator refusal a test against the same join the curve
    reads.
    """
    provider, model, policy = source

    def generate(*, prompt, brain, sample):
        return Completion(
            text=f"{prompt} answered from: {brain.profile.strip()[:20]} #{sample}",
            model_call_id=recorder.record_model_call(
                provider=provider,
                model=model,
                policy=policy,
                prompt_tokens=8,
                completion_tokens=16,
            ),
            prompt_tokens=8,
            completion_tokens=16,
        )

    return generate


@pytest.fixture
def generate(recorder):
    return _generator(recorder)


@pytest.fixture
def generate_in_the_cloud(recorder):
    return _generator(recorder, CLOUD)


class TestContent:
    def test_real_candidates_parse(self):
        """The shipped candidate file must actually parse, wherever it is checked out."""
        candidates = REPO_ROOT / "config" / "evals" / "candidates.md"
        found = load_prompts(candidates)
        assert len(found) == 10
        assert all(c.prompt and c.slug for c in found)

    def test_prose_without_a_prompt_is_skipped(self, tmp_path):
        path = tmp_path / "c.md"
        path.write_text("### 1. Real\n\n> the prompt\n\n### 2. Just prose\n\nno quote here\n")
        assert [c.slug for c in load_prompts(path)] == ["real"]

    def test_rubric_hash_follows_content(self, tmp_path):
        path = tmp_path / "r.md"
        path.write_text("one")
        first = load_rubric(path).sha
        path.write_text("two")
        assert load_rubric(path).sha != first


class TestSelection:
    def test_candidates_load_inactive(self, runner, rubric, repo):
        _seed_and_activate(runner, rubric, slugs=())
        from secondshift.evals.content import PromptCandidate

        runner.load_candidates(
            [PromptCandidate(slug=s, label=s, prompt=f"p {s}") for s in ("x", "y")], rubric
        )
        assert runner.active_prompts() == []
        assert repo.connection.execute(
            "SELECT COUNT(*) n FROM eval_prompts"
        ).fetchone()["n"] == 2

    def test_selection_does_not_delete_the_reserve(self, runner, rubric, repo):
        from secondshift.evals.content import PromptCandidate

        runner.load_candidates(
            [PromptCandidate(slug=s, label=s, prompt=f"p {s}") for s in "abcde"], rubric
        )
        runner.activate(["a", "b"])
        assert [s for _, s, _ in runner.active_prompts()] == ["a", "b"]
        assert repo.connection.execute(
            "SELECT COUNT(*) n FROM eval_prompts"
        ).fetchone()["n"] == 5

    def test_loading_twice_does_not_duplicate(self, runner, rubric):
        from secondshift.evals.content import PromptCandidate

        candidates = [PromptCandidate(slug="a", label="a", prompt="p")]
        assert runner.load_candidates(candidates, rubric) == 1
        assert runner.load_candidates(candidates, rubric) == 0


class TestJudgement:
    def test_valid_scores_parse(self):
        assert Judgement.parse({"scores": GOOD}).total == 20

    def test_missing_dimension_is_unreadable(self):
        partial = {d: 4 for d in DIMENSIONS[:-1]}
        with pytest.raises(UnreadableJudgement, match="missing dimension"):
            Judgement.parse({"scores": partial})

    def test_out_of_range_is_unreadable(self):
        with pytest.raises(UnreadableJudgement, match="outside"):
            Judgement.parse({"scores": {**GOOD, "voice": 9}})

    def test_prose_is_unreadable(self):
        with pytest.raises(UnreadableJudgement):
            Judgement.parse("it was pretty good, maybe a 4")

    def test_boolean_is_not_a_score(self):
        with pytest.raises(UnreadableJudgement, match="not a whole number"):
            Judgement.parse({"scores": {**GOOD, "fit": True}})


class TestBaselineAndPinning:
    def test_baseline_records_inputs_without_a_judge(self, runner, rubric, repo, brain):
        _seed_and_activate(runner, rubric)
        run_id = runner.record_baseline(week_of="2026-08-24", rubric=rubric)
        row = repo.connection.execute(
            "SELECT * FROM eval_runs WHERE id = ?", (run_id,)
        ).fetchone()
        assert row["brain_sha"] == brain.head()
        assert row["rubric_sha"] == rubric.sha
        assert row["judge_model"] == AWAITING
        assert runner.awaiting_scoring() == [run_id]

    def test_scoring_reads_the_brain_at_the_recorded_commit(
        self, runner, rubric, brain
    ):
        """The point of pinning: generate from week one, not from today."""
        _seed_and_activate(runner, rubric)
        run_id = runner.record_baseline(week_of="2026-08-24", rubric=rubric)
        baseline_sha = brain.head()

        # The brain moves on.
        (brain.path / "profile.md").write_text("# Profile\n\nWeek eight belief.\n")
        subprocess.run(["git", "-C", str(brain.path), "commit", "-qam", "later"],
                       check=True, capture_output=True)
        assert brain.head() != baseline_sha

        recalled = runner.brain_at_baseline(run_id)
        assert "Week one belief" in recalled.profile
        assert "Week eight" not in recalled.profile

    def test_scoring_does_not_overwrite_the_recorded_commit(
        self, runner, rubric, repo, brain, generate
    ):
        _seed_and_activate(runner, rubric)
        run_id = runner.record_baseline(week_of="2026-08-24", rubric=rubric)
        baseline_sha = brain.head()
        (brain.path / "profile.md").write_text("# Profile\n\nlater\n")
        subprocess.run(["git", "-C", str(brain.path), "commit", "-qam", "later"],
                       check=True, capture_output=True)

        runner.score(run_id, judge=StubJudge(), generate=generate, rubric=rubric)
        row = repo.connection.execute(
            "SELECT brain_sha FROM eval_runs WHERE id = ?", (run_id,)
        ).fetchone()
        assert row["brain_sha"] == baseline_sha

    def test_a_baseline_without_a_brain_is_refused(self, repo, rubric, tmp_path):
        """The schema forbids a null commit; refuse clearly rather than opaquely."""
        runner = EvalRunner(repo, brain=BrainRepo(tmp_path / "absent"), samples=3)
        _seed_and_activate(runner, rubric)
        with pytest.raises(BrainUnavailable, match="measures nothing"):
            runner.record_baseline(week_of="2026-08-24", rubric=rubric)

    def test_no_partial_run_is_left_behind_by_that_refusal(self, repo, rubric, tmp_path):
        runner = EvalRunner(repo, brain=BrainRepo(tmp_path / "absent"), samples=3)
        _seed_and_activate(runner, rubric)
        with pytest.raises(BrainUnavailable):
            runner.record_baseline(week_of="2026-08-24", rubric=rubric)
        assert repo.connection.execute(
            "SELECT COUNT(*) n FROM eval_runs"
        ).fetchone()["n"] == 0


class TestSampling:
    def test_three_samples_per_prompt(self, runner, rubric, repo, generate):
        _seed_and_activate(runner, rubric)
        run_id = runner.record_baseline(week_of="2026-08-24", rubric=rubric)
        runner.score(run_id, judge=StubJudge(), generate=generate, rubric=rubric)
        rows = repo.connection.execute(
            "SELECT eval_prompt_id, sample_index FROM eval_results WHERE eval_run_id = ?",
            (run_id,),
        ).fetchall()
        assert len(rows) == 6
        assert sorted({r["sample_index"] for r in rows}) == [0, 1, 2]

    def test_summary_reports_a_center_and_a_spread(self, runner, rubric, generate):
        _seed_and_activate(runner, rubric)
        run_id = runner.record_baseline(week_of="2026-08-24", rubric=rubric)
        summary = runner.score(run_id, judge=StubJudge(), generate=generate, rubric=rubric)
        assert len(summary.prompts) == 2
        for prompt in summary.prompts:
            assert len(prompt.samples) == 3
            assert prompt.mean > 0
            assert prompt.spread >= 0
        assert summary.complete is True

    def test_pinning_is_recorded_on_the_run(self, runner, rubric, repo, generate):
        _seed_and_activate(runner, rubric)
        run_id = runner.record_baseline(week_of="2026-08-24", rubric=rubric)
        judge = StubJudge()
        runner.score(run_id, judge=judge, generate=generate, rubric=rubric)
        row = repo.connection.execute(
            "SELECT judge_model, judge_model_version, rubric_sha FROM eval_runs WHERE id = ?",
            (run_id,),
        ).fetchone()
        assert row["judge_model"] == judge.name
        assert row["judge_model_version"] == judge.version
        assert row["rubric_sha"] == rubric.sha

    def test_subscores_are_recorded_per_dimension(self, runner, rubric, repo, generate):
        _seed_and_activate(runner, rubric)
        run_id = runner.record_baseline(week_of="2026-08-24", rubric=rubric)
        runner.score(run_id, judge=StubJudge(), generate=generate, rubric=rubric)
        row = repo.connection.execute(
            "SELECT subscores_json FROM eval_results WHERE eval_run_id = ? LIMIT 1",
            (run_id,),
        ).fetchone()
        assert set(json.loads(row["subscores_json"])) == set(DIMENSIONS)


class TestFailureHandling:
    def test_no_judge_configured_refuses(self, runner, rubric, generate):
        _seed_and_activate(runner, rubric)
        run_id = runner.record_baseline(week_of="2026-08-24", rubric=rubric)
        with pytest.raises(NoJudgeConfigured, match="refusing"):
            runner.score(run_id, judge=None, generate=generate, rubric=rubric)

    def test_an_unreadable_judgement_records_a_failure_not_a_zero(
        self, runner, rubric, repo, generate
    ):
        class Broken(StubJudge):
            def score(self, *, output, rubric, prompt):
                raise UnreadableJudgement("returned prose")

        _seed_and_activate(runner, rubric, slugs=("a",))
        run_id = runner.record_baseline(week_of="2026-08-24", rubric=rubric)
        summary = runner.score(run_id, judge=Broken(), generate=generate, rubric=rubric)

        assert summary.prompts == []
        assert summary.complete is False
        failures = repo.connection.execute(
            "SELECT type, message FROM failures"
        ).fetchall()
        assert len(failures) == 3
        assert all(f["type"] == "bad_output" for f in failures)

    def test_a_partial_run_records_its_successes(self, runner, rubric, generate):
        calls = {"n": 0}

        class Flaky(StubJudge):
            def score(self, *, output, rubric, prompt):
                calls["n"] += 1
                if calls["n"] == 2:
                    raise UnreadableJudgement("one bad sample")
                return Judgement(scores=GOOD)

        _seed_and_activate(runner, rubric, slugs=("a",))
        run_id = runner.record_baseline(week_of="2026-08-24", rubric=rubric)
        summary = runner.score(run_id, judge=Flaky(), generate=generate, rubric=rubric)

        assert summary.prompts[0].samples == [20, 20]
        assert summary.complete is False

    def test_an_incomplete_run_is_evident(self, runner, rubric):
        _seed_and_activate(runner, rubric)
        run_id = runner.record_baseline(week_of="2026-08-24", rubric=rubric)
        assert runner.summarize(run_id).complete is False


class TestExplicitSlugs:
    """A slug names the prompt. Derived ones name the argument for choosing it."""

    def test_an_explicit_slug_is_used(self, tmp_path):
        path = tmp_path / "c.md"
        path.write_text("### 1. Vague by design — tests interrogation {#repeat-mistake}\n\n> the prompt\n")
        found = load_prompts(path)
        assert [c.slug for c in found] == ["repeat-mistake"]

    def test_the_marker_is_stripped_from_the_label(self, tmp_path):
        path = tmp_path / "c.md"
        path.write_text("### 1. Vague by design {#repeat-mistake}\n\n> the prompt\n")
        assert load_prompts(path)[0].label == "Vague by design"

    def test_a_heading_without_one_still_derives(self, tmp_path):
        path = tmp_path / "c.md"
        path.write_text("### 1. Some Label Here\n\n> the prompt\n")
        assert load_prompts(path)[0].slug == "some-label-here"

    def test_the_shipped_candidates_all_name_themselves(self):
        found = load_prompts(REPO_ROOT / "config" / "evals" / "candidates.md")
        slugs = {c.slug for c in found}
        assert len(slugs) == 10
        # Every slug names what the prompt asks, not why it was chosen.
        assert "readme-in-my-voice" in slugs
        assert not any("tests-" in s for s in slugs)


class TestRubricPinningIsBinding:
    """The pinned hash was recorded and then trusted. Now it is checked."""

    def _drifted(self, tmp_path) -> Rubric:
        """A rubric that is not the one a baseline pinned.

        Written as a separate file rather than by editing the fixture in place,
        because editing a rubric in place is exactly what the rubric forbids and
        what this guard exists to catch.
        """
        path = tmp_path / "rubric-drifted.md"
        path.write_text("# Rubric v1\n\nFive dimensions, one to five. Plus a sixth.\n")
        return load_rubric(path)

    def test_scoring_under_a_different_rubric_is_refused(self, runner, rubric, tmp_path, generate):
        _seed_and_activate(runner, rubric)
        run_id = runner.record_baseline(week_of="2026-08-24", rubric=rubric)
        drifted = self._drifted(tmp_path)

        with pytest.raises(RubricMismatch) as raised:
            runner.score(run_id, judge=StubJudge(), generate=generate, rubric=drifted)

        # Both hashes named: a refusal that does not say which two values
        # disagree leaves the operator running the same SQL by hand.
        message = str(raised.value)
        assert rubric.sha[:12] in message
        assert drifted.sha[:12] in message

    def test_a_refused_score_records_nothing(self, runner, rubric, repo, tmp_path, generate):
        _seed_and_activate(runner, rubric)
        run_id = runner.record_baseline(week_of="2026-08-24", rubric=rubric)

        with pytest.raises(RubricMismatch):
            runner.score(
                run_id, judge=StubJudge(), generate=generate,
                rubric=self._drifted(tmp_path),
            )

        assert repo.connection.execute(
            "SELECT COUNT(*) n FROM eval_results WHERE eval_run_id = ?", (run_id,)
        ).fetchone()["n"] == 0
        assert runner.awaiting_scoring() == [run_id]

    def test_a_refusal_is_not_recorded_as_failed_samples(
        self, runner, rubric, repo, tmp_path, generate
    ):
        """A wrong rubric is wrong for every sample, so it is not a partial run."""
        _seed_and_activate(runner, rubric)
        run_id = runner.record_baseline(week_of="2026-08-24", rubric=rubric)
        before = repo.connection.execute("SELECT COUNT(*) n FROM failures").fetchone()["n"]

        with pytest.raises(RubricMismatch):
            runner.score(
                run_id, judge=StubJudge(), generate=generate,
                rubric=self._drifted(tmp_path),
            )

        after = repo.connection.execute("SELECT COUNT(*) n FROM failures").fetchone()["n"]
        assert after == before

    def test_the_refusal_happens_before_anything_is_generated(
        self, runner, rubric, tmp_path
    ):
        """Generation is where the cost is. The check is cheaper and comes first."""
        calls: list[str] = []

        def _record(prompt: str, brain, sample: int) -> str:
            calls.append(prompt)
            return "answer"

        _seed_and_activate(runner, rubric)
        run_id = runner.record_baseline(week_of="2026-08-24", rubric=rubric)
        with pytest.raises(RubricMismatch):
            runner.score(
                run_id, judge=StubJudge(), generate=_record,
                rubric=self._drifted(tmp_path),
            )
        assert calls == []

    def test_scoring_under_the_pinned_rubric_proceeds(self, runner, rubric, repo, generate):
        _seed_and_activate(runner, rubric)
        run_id = runner.record_baseline(week_of="2026-08-24", rubric=rubric)
        summary = runner.score(run_id, judge=StubJudge(), generate=generate, rubric=rubric)
        assert summary.complete
        assert repo.connection.execute(
            "SELECT COUNT(*) n FROM eval_results WHERE eval_run_id = ?", (run_id,)
        ).fetchone()["n"] == 6

    def test_an_identical_rubric_at_another_path_is_the_same_rubric(
        self, runner, rubric, tmp_path, generate
    ):
        """The hash follows content, not location. A copy is not drift."""
        elsewhere = tmp_path / "copied" / "rubric.md"
        elsewhere.parent.mkdir()
        elsewhere.write_text(rubric.text)

        _seed_and_activate(runner, rubric)
        run_id = runner.record_baseline(week_of="2026-08-24", rubric=rubric)
        summary = runner.score(
            run_id, judge=StubJudge(), generate=generate, rubric=load_rubric(elsewhere)
        )
        assert summary.complete


class TestStatusReportsThePinning:
    """`status` hashed the file it had just read and exited zero either way.

    That is the one value that cannot reveal a disagreement with what a run
    pinned, which is how a mismatch stayed invisible in its output.
    """

    def _run(self, tmp_path, rubric_path, capsys) -> tuple[int, str]:
        code = main([
            "status",
            "--db", str(tmp_path / "second-shift.db"),
            "--rubric", str(rubric_path),
            "--brain", str(tmp_path / "brain"),
        ])
        return code, capsys.readouterr().out

    def test_a_recorded_run_reports_what_it_pinned(
        self, runner, rubric, brain, tmp_path, capsys
    ):
        _seed_and_activate(runner, rubric)
        run_id = runner.record_baseline(week_of="2026-08-24", rubric=rubric)

        code, out = self._run(tmp_path, rubric.path, capsys)

        assert code == 0
        assert run_id in out
        assert "2026-08-24" in out
        assert rubric.sha[:12] in out
        assert brain.head()[:12] in out
        assert "awaiting scoring" in out
        assert "every recorded run pinned the rubric on disk" in out

    def test_a_run_pinned_to_another_rubric_is_called_out(
        self, runner, rubric, tmp_path, capsys
    ):
        _seed_and_activate(runner, rubric)
        run_id = runner.record_baseline(week_of="2026-08-24", rubric=rubric)

        # The file drifts after the baseline — the case that actually happened.
        rubric.path.write_text("# Rubric v1\n\nSix dimensions now.\n")
        on_disk = load_rubric(rubric.path)
        assert on_disk.sha != rubric.sha

        code, out = self._run(tmp_path, rubric.path, capsys)

        assert code == 1
        assert "not the rubric on disk" in out
        assert f"run {run_id} pinned rubric {rubric.sha[:12]}" in out
        assert on_disk.sha[:12] in out
        assert "superseded, never edited in place" in out

    def test_an_empty_database_reports_the_rubric_and_exits_zero(
        self, runner, rubric, tmp_path, capsys
    ):
        code, out = self._run(tmp_path, rubric.path, capsys)
        assert code == 0
        assert rubric.sha[:12] in out
        assert "no recorded run has pinned it yet" in out

    def test_the_active_set_is_still_reported(self, runner, rubric, tmp_path, capsys):
        _seed_and_activate(runner, rubric, slugs=("alpha", "beta"))
        code, out = self._run(tmp_path, rubric.path, capsys)
        assert code == 0
        assert "2 active prompts" in out
        assert "alpha" in out and "beta" in out

    def test_a_scored_run_names_its_judge_rather_than_awaiting(
        self, runner, rubric, tmp_path, capsys, generate
    ):
        _seed_and_activate(runner, rubric)
        run_id = runner.record_baseline(week_of="2026-08-24", rubric=rubric)
        runner.score(run_id, judge=StubJudge(), generate=generate, rubric=rubric)

        code, out = self._run(tmp_path, rubric.path, capsys)
        assert code == 0
        assert "judged by stub-judge" in out
        assert "awaiting scoring" not in out


class TestAJudgeDeploymentCannotScoreItselfIntoTheCurve:
    """The eval tables had no `is_synthetic` column at all until 19 Sep, and the
    runner never filtered on one.

    Ten other accumulating tables carried the flag and the rollup views excluded
    it. These three did not, so an evaluation run on a judge deployment wrote
    unmarked rows straight into the curve the whole submission rests on — and
    nothing would have shown it afterwards, because a synthetic score is a
    number like any other once it is in the table.
    """

    @pytest.fixture
    def demo(self, repo, brain) -> EvalRunner:
        """A runner as a judge deployment constructs one."""
        return EvalRunner(repo, brain=brain, samples=3, is_synthetic=True)

    def test_a_synthetic_deployment_marks_the_prompts_it_loads(
        self, demo, rubric, repo
    ):
        _seed_and_activate(demo, rubric)

        flags = {
            r["is_synthetic"]
            for r in repo.connection.execute("SELECT is_synthetic FROM eval_prompts")
        }

        assert flags == {1}

    def test_a_synthetic_deployment_marks_the_run_it_opens(
        self, demo, rubric, repo
    ):
        _seed_and_activate(demo, rubric)
        run_id = demo.record_baseline(week_of="2026-09-21", rubric=rubric)

        row = repo.connection.execute(
            "SELECT is_synthetic FROM eval_runs WHERE id = ?", (run_id,)
        ).fetchone()

        assert row["is_synthetic"] == 1

    def test_the_personal_instance_marks_nothing(self, runner, rubric, repo):
        """The negative half, and the one that makes the flag mean something:
        without it the rule could be `True` everywhere and both tests above
        would still pass."""
        _seed_and_activate(runner, rubric)
        run_id = runner.record_baseline(week_of="2026-09-21", rubric=rubric)

        assert not repo.connection.execute(
            "SELECT is_synthetic FROM eval_runs WHERE id = ?", (run_id,)
        ).fetchone()["is_synthetic"]
        assert {
            r["is_synthetic"]
            for r in repo.connection.execute("SELECT is_synthetic FROM eval_prompts")
        } == {0}

    def test_a_synthetic_run_is_not_in_the_curve(
        self, runner, demo, rubric, repo
    ):
        """The measurement itself. A demo instance's run must not appear among
        the runs a week-over-week comparison walks."""
        _seed_and_activate(runner, rubric)
        real = runner.record_baseline(week_of="2026-09-21", rubric=rubric)
        fake = demo.record_baseline(week_of="2026-09-21", rubric=rubric)

        listed = {r.eval_run_id for r in runner.recorded_runs()}

        assert real in listed
        assert fake not in listed

    def test_a_synthetic_run_is_not_offered_for_scoring(
        self, runner, demo, rubric
    ):
        """`awaiting_scoring` is what a person reaches for to finish a week.
        Offering a demo's run there is how one gets scored by accident."""
        _seed_and_activate(runner, rubric)
        real = runner.record_baseline(week_of="2026-09-21", rubric=rubric)
        fake = demo.record_baseline(week_of="2026-09-21", rubric=rubric)

        waiting = set(runner.awaiting_scoring())

        assert real in waiting
        assert fake not in waiting

    def test_every_eval_table_carries_the_flag(self, repo):
        """Read from the schema rather than listed, so a fourth eval table added
        by a later migration is audited the day it appears."""
        names = [
            r["name"]
            for r in repo.connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' "
                "AND name LIKE 'eval_%'"
            )
        ]

        assert names
        for name in names:
            columns = {
                c["name"] for c in repo.connection.execute(f"PRAGMA table_info({name})")
            }
            assert "is_synthetic" in columns, f"{name} can hold unmarked rows"


class TestTheCurveRefusesMoreThanItReports:
    """The submission's centerpiece is a comparison, and comparisons go wrong
    quietly. Every refusal here is a way the reported number would measure
    something other than what it appears to."""

    @pytest.fixture
    def two_runs(self, runner, rubric, brain, generate):
        """Two scored runs over two brain states, which is the only shape that
        is actually comparable."""
        _seed_and_activate(runner, rubric)
        first = runner.record_baseline(week_of="2026-08-31", rubric=rubric)
        runner.score(first, judge=_FixedJudge(GOOD), generate=generate, rubric=rubric)

        (Path(brain.path) / "profile.md").write_text("# Profile\n\nWeek eight belief.\n")
        for args in (["add", "-A"], ["commit", "-q", "-m", "week eight"]):
            subprocess.run(["git", "-C", str(brain.path), *args], check=True, capture_output=True)

        second = runner.record_baseline(week_of="2026-10-19", rubric=rubric)
        runner.score(second, judge=_FixedJudge({d: 5 for d in DIMENSIONS}), generate=generate, rubric=rubric)
        return first, second

    def test_two_comparable_runs_produce_a_curve(self, runner, two_runs):
        first, second = two_runs

        curve = runner.curve(first, second)

        assert curve.difference > 0
        assert len(curve.dimensions) == len(DIMENSIONS)

    def test_the_difference_is_reported_against_the_spread(self, runner, two_runs):
        """A difference without a spread is the version that gets screenshotted."""
        first, second = two_runs

        curve = runner.curve(first, second)

        assert curve.spread == 0.0, "the stub judge is deterministic, so there is no spread"
        assert curve.moved is True

    def test_a_difference_inside_the_noise_is_not_a_change(self, runner, rubric, brain, generate):
        """A real difference, and still not a change.

        The first draft of this test used two judges whose means were exactly
        equal, so `moved` was False for the wrong reason — replacing the spread
        comparison with `difference != 0` left it green. A test for "inside the
        noise" needs a difference that is not zero.
        """
        _seed_and_activate(runner, rubric)
        first = runner.record_baseline(week_of="2026-08-31", rubric=rubric)
        runner.score(first, judge=_VaryingJudge([1, 5, 3]), generate=generate, rubric=rubric)

        (Path(brain.path) / "profile.md").write_text("# Profile\n\nLater.\n")
        for args in (["add", "-A"], ["commit", "-q", "-m", "later"]):
            subprocess.run(["git", "-C", str(brain.path), *args], check=True, capture_output=True)
        second = runner.record_baseline(week_of="2026-10-19", rubric=rubric)
        runner.score(second, judge=_VaryingJudge([3, 4, 3]), generate=generate, rubric=rubric)

        curve = runner.curve(first, second)

        assert curve.difference != 0, "a zero difference would prove nothing here"
        assert abs(curve.difference) < curve.spread
        assert curve.moved is False

    def test_the_same_brain_is_refused(self, runner, rubric, generate):
        """The one most likely to happen by accident: run the week-8 eval
        without the brain having moved, and the curve reports sampling noise."""
        _seed_and_activate(runner, rubric)
        first = runner.record_baseline(week_of="2026-08-31", rubric=rubric)
        runner.score(first, judge=_FixedJudge(GOOD), generate=generate, rubric=rubric)
        second = runner.record_baseline(week_of="2026-10-19", rubric=rubric)
        runner.score(second, judge=_FixedJudge(GOOD), generate=generate, rubric=rubric)

        with pytest.raises(NotComparable, match="brain did not change"):
            runner.curve(first, second)

    def test_a_different_rubric_is_refused(self, runner, rubric, two_runs, tmp_path, repo):
        first, second = two_runs
        repo.connection.execute(
            "UPDATE eval_runs SET rubric_sha = 'deadbeefdeadbeef' WHERE id = ?", (second,)
        )

        with pytest.raises(NotComparable, match="different rubrics"):
            runner.curve(first, second)

    def test_a_different_judge_is_refused(self, runner, two_runs, repo):
        """Two judges are two instruments."""
        first, second = two_runs
        repo.connection.execute(
            "UPDATE eval_runs SET judge_model = 'some-other-model' WHERE id = ?", (second,)
        )

        with pytest.raises(NotComparable, match="different judges"):
            runner.curve(first, second)

    def test_an_incomplete_run_is_refused(self, runner, two_runs, repo):
        """Averaging over the samples that survived hides which prompts did not."""
        first, second = two_runs
        repo.connection.execute(
            "DELETE FROM eval_results WHERE eval_run_id = ? AND sample_index = 2", (second,)
        )

        with pytest.raises(NotComparable, match="incomplete"):
            runner.curve(first, second)

    def test_a_synthetic_run_is_refused(self, runner, two_runs, repo):
        first, second = two_runs
        repo.connection.execute("UPDATE eval_runs SET is_synthetic = 1 WHERE id = ?", (second,))

        with pytest.raises(NotComparable, match="synthetic"):
            runner.curve(first, second)

    def test_an_unscored_run_is_refused(self, runner, rubric, two_runs):
        first, _ = two_runs
        unscored = runner.record_baseline(week_of="2026-10-19", rubric=rubric)

        with pytest.raises(NotComparable, match="never scored"):
            runner.curve(first, unscored)

    def test_a_regression_hidden_by_the_mean_is_visible(self, runner, rubric, brain, generate):
        """The case the per-dimension breakdown exists for, and the one that will
        not occur by accident in a fixture: the overall mean improves while one
        dimension goes backwards."""
        _seed_and_activate(runner, rubric)
        first = runner.record_baseline(week_of="2026-08-31", rubric=rubric)
        runner.score(
            first,
            judge=_FixedJudge({**{d: 3 for d in DIMENSIONS}, "voice": 5}),
            generate=generate,
            rubric=rubric,
        )

        (Path(brain.path) / "profile.md").write_text("# Profile\n\nLouder.\n")
        for args in (["add", "-A"], ["commit", "-q", "-m", "louder"]):
            subprocess.run(["git", "-C", str(brain.path), *args], check=True, capture_output=True)
        second = runner.record_baseline(week_of="2026-10-19", rubric=rubric)
        runner.score(
            second,
            judge=_FixedJudge({**{d: 5 for d in DIMENSIONS}, "voice": 1}),
            generate=generate,
            rubric=rubric,
        )

        curve = runner.curve(first, second)
        voice = next(d for d in curve.dimensions if d.dimension == "voice")

        assert curve.difference > 0, "the overall mean improved"
        assert voice.difference < 0, "and voice regressed, which the mean hides"
        assert curve.agreeing_dimensions == len(DIMENSIONS) - 1


class _FixedJudge:
    """The same per-dimension scores every time.

    `StubJudge` varies its scores with the output on purpose, so a test can tell
    one result from another. A curve needs the opposite: the difference between
    two runs is the thing under test, so everything else has to hold still.
    """

    name = "fixed"
    version = "1"

    def __init__(self, scores: dict[str, int]) -> None:
        self._scores = dict(scores)

    def score(self, *, output: str, rubric: str, prompt: str) -> Judgement:
        return Judgement(dict(self._scores))


class _VaryingJudge:
    """A judge whose scores vary by sample, so a spread exists to compare against."""

    name = "varying"
    version = "1"

    def __init__(self, scores: list[int]) -> None:
        self._scores = scores
        self._calls = 0

    def score(self, *, output: str, rubric: str, prompt: str) -> Judgement:
        value = self._scores[self._calls % len(self._scores)]
        self._calls += 1
        return Judgement({d: value for d in DIMENSIONS})


class TestTheCurveCommand:
    """`status` once printed the hash of the file it had just read and exited
    zero either way. The curve's exit code is part of its report for the same
    reason: this output goes into a submission, and "it printed something" is
    not the same as "there was something to print"."""

    def _run(self, tmp_path, rubric_path, *args) -> int:
        return main([
            "curve",
            *args,
            "--db", str(tmp_path / "second-shift.db"),
            "--rubric", str(rubric_path),
            "--brain", str(tmp_path / "brain"),
        ])

    def test_nothing_to_compare_exits_non_zero(self, runner, rubric, tmp_path, capsys):
        """Today's real answer, and the one it must not dress up as a report."""
        code = self._run(tmp_path, rubric.path)

        assert code == 1
        assert "nothing to compare yet" in capsys.readouterr().err

    def test_one_scored_run_is_still_not_a_curve(self, runner, rubric, tmp_path, capsys, generate):
        _seed_and_activate(runner, rubric)
        run_id = runner.record_baseline(week_of="2026-08-31", rubric=rubric)
        runner.score(run_id, judge=StubJudge(), generate=generate, rubric=rubric)

        code = self._run(tmp_path, rubric.path)

        assert code == 1
        assert "1 scored run" in capsys.readouterr().err

    def test_a_refusal_is_reported_on_stderr_and_exits_non_zero(
        self, runner, rubric, tmp_path, capsys, generate
    ):
        _seed_and_activate(runner, rubric)
        first = runner.record_baseline(week_of="2026-08-31", rubric=rubric)
        runner.score(first, judge=StubJudge(), generate=generate, rubric=rubric)
        second = runner.record_baseline(week_of="2026-10-19", rubric=rubric)
        runner.score(second, judge=StubJudge(), generate=generate, rubric=rubric)

        code = self._run(tmp_path, rubric.path)

        assert code == 1
        assert "brain did not change" in capsys.readouterr().err

    def test_a_comparison_prints_the_spread_beside_the_difference(
        self, runner, rubric, brain, tmp_path, capsys, generate
    ):
        """There is no output shape that shows a difference without its spread."""
        _seed_and_activate(runner, rubric)
        first = runner.record_baseline(week_of="2026-08-31", rubric=rubric)
        runner.score(first, judge=_FixedJudge({d: 3 for d in DIMENSIONS}),
                     generate=generate, rubric=rubric)
        (Path(brain.path) / "profile.md").write_text("# Profile\n\nLater.\n")
        for args in (["add", "-A"], ["commit", "-q", "-m", "later"]):
            subprocess.run(["git", "-C", str(brain.path), *args], check=True, capture_output=True)
        second = runner.record_baseline(week_of="2026-10-19", rubric=rubric)
        runner.score(second, judge=_FixedJudge({d: 5 for d in DIMENSIONS}),
                     generate=generate, rubric=rubric)

        code = self._run(tmp_path, rubric.path)
        out = capsys.readouterr().out

        assert code == 0
        assert "difference" in out and "spread" in out
        assert "dimensions moved the same way" in out
        for dimension in DIMENSIONS:
            assert dimension in out

    def test_two_identifiers_are_taken_in_order(self, runner, rubric, tmp_path, capsys, generate):
        """A wrong pair compared by hand is the failure the no-argument form avoids."""
        _seed_and_activate(runner, rubric)
        first = runner.record_baseline(week_of="2026-08-31", rubric=rubric)
        runner.score(first, judge=StubJudge(), generate=generate, rubric=rubric)

        code = self._run(tmp_path, rubric.path, first, first)

        assert code == 1
        assert "brain did not change" in capsys.readouterr().err

    def test_one_identifier_is_refused_as_a_usage_error(self, runner, rubric, tmp_path, capsys):
        code = self._run(tmp_path, rubric.path, "only-one")

        assert code == 2
        assert "two eval run ids" in capsys.readouterr().err


REPO_THRESHOLD = REPO_ROOT / "config" / "evals" / "threshold.md"


class TestTheBarWasSetBeforeTheNumber:
    """`EVAL_SCORING.md`: a threshold chosen after the fact is not a
    measurement, and a judge who has run an experiment will know."""

    def test_the_shipped_threshold_says_when_it_was_fixed(self):
        """A date in the text, not a modification time — that is a property of
        a checkout and this has to survive being cloned."""
        threshold = load_threshold(REPO_THRESHOLD)

        assert threshold.fixed_on == "2026-09-23"

    def test_a_threshold_that_does_not_say_when_is_refused(self, tmp_path):
        path = tmp_path / "t.md"
        path.write_text("# A bar\n\nTwo standard errors.\n")

        with pytest.raises(ValueError, match="does not say when it was fixed"):
            load_threshold(path).fixed_on

    def test_the_hash_follows_the_text(self, tmp_path):
        """An edit after the result changes the hash, and the hash is printed
        beside the verdict."""
        path = tmp_path / "t.md"
        path.write_text("**Fixed 2026-09-23** two errors\n")
        first = load_threshold(path).sha
        path.write_text("**Fixed 2026-09-23** one error\n")

        assert load_threshold(path).sha != first

    def test_the_rule_matches_the_file(self):
        """The numbers live in code and the argument lives in the file, so this
        is the seam where they could disagree."""
        threshold = load_threshold(REPO_THRESHOLD)

        assert threshold.standard_errors == 2.0
        assert "twice its standard error" in threshold.text
        assert "two thirds" in threshold.text
        assert abs(threshold.agreeing_share - 2 / 3) < 1e-9

    def test_the_file_records_the_correction_it_makes(self):
        """It supersedes what 2026-09-21-add-eval-curve recommended, and says
        so rather than quietly shipping the better rule."""
        text = load_threshold(REPO_THRESHOLD).text

        assert "standard deviation describes the spread of samples" in text
        assert "no p-value is computed" in text


class TestTheVerdict:
    """Constructed so the rule decides each case rather than the fixture being
    obviously one-sided."""

    def _curve(self, prompts, threshold=None):
        from secondshift.evals.runner import Curve, PromptDelta, RunSummary

        empty = RunSummary(
            eval_run_id="x", brain_sha="a", rubric_sha="r", judge_model="j", complete=True
        )
        return Curve(
            earlier=empty,
            later=empty,
            dimensions=[],
            prompts=[PromptDelta(slug=s, earlier=e, later=l) for s, e, l in prompts],
            threshold=threshold or load_threshold(REPO_THRESHOLD),
        )

    def test_a_consistent_gain_clears_the_bar(self):
        curve = self._curve([(f"p{i}", 15.0, 17.0 + i * 0.1) for i in range(6)])

        assert curve.verdict == IMPROVED
        assert curve.agreeing_prompts == 6

    def test_one_prompt_carrying_the_mean_does_not(self):
        """The case pairing exists for. The pooled mean moves by a point, and
        one prompt is the entire reason."""
        deltas = [("p0", 15.0, 15.1), ("p1", 15.0, 15.1), ("p2", 15.0, 15.1),
                  ("p3", 15.0, 15.1), ("p4", 15.0, 15.1), ("p5", 15.0, 21.0)]
        curve = self._curve(deltas)

        assert curve.paired_difference > 1.0, "the mean did move"
        assert curve.verdict == NO_IMPROVEMENT_SHOWN, "and it is one prompt's doing"

    def test_a_consistent_loss_is_reported_as_one(self):
        """With the same prominence. A thesis that cannot fail is not a
        measurement."""
        curve = self._curve([(f"p{i}", 17.0 + i * 0.1, 15.0) for i in range(6)])

        assert curve.verdict == REGRESSED

    def test_a_split_decision_does_not_clear_the_consistency_bar(self):
        """Three up, three barely down — and the magnitude bar is cleared.

        The first version of this test used three large gains against three
        small losses, which fails on magnitude alone: a split inflates the
        spread of the differences and the standard error with it. So dropping
        the consistency condition entirely left every test green, which is what
        the mutation pass is for. These numbers clear the first condition (mean
        0.50 against a standard error of 0.23) and fail only the second, which
        is the isolation this test is supposed to provide.
        """
        deltas = [("p0", 15.0, 16.0), ("p1", 15.0, 16.0), ("p2", 15.0, 16.0),
                  ("p3", 15.0, 14.99), ("p4", 15.0, 14.99), ("p5", 15.0, 14.99)]
        curve = self._curve(deltas)
        threshold = load_threshold(REPO_THRESHOLD)

        assert abs(curve.paired_difference) > threshold.standard_errors * curve.standard_error, (
            "this case no longer clears the magnitude bar, so it no longer "
            "isolates the consistency one"
        )
        assert curve.agreeing_prompts == 3
        assert curve.verdict == NO_IMPROVEMENT_SHOWN

    def test_no_threshold_means_no_verdict_claimed(self):
        from secondshift.evals.runner import Curve, PromptDelta, RunSummary

        empty = RunSummary(
            eval_run_id="x", brain_sha="a", rubric_sha="r", judge_model="j", complete=True
        )
        curve = Curve(
            earlier=empty,
            later=empty,
            dimensions=[],
            prompts=[PromptDelta(slug="p", earlier=1.0, later=9.0)],
            threshold=None,
        )

        assert curve.verdict == NO_IMPROVEMENT_SHOWN

    def test_the_standard_error_is_not_the_standard_deviation(self):
        """The specific error this threshold corrects. With six prompts they
        differ by a factor of the square root of six."""
        import statistics

        deltas = [("p0", 0.0, 1.0), ("p1", 0.0, 2.0), ("p2", 0.0, 3.0),
                  ("p3", 0.0, 4.0), ("p4", 0.0, 5.0), ("p5", 0.0, 6.0)]
        curve = self._curve(deltas)
        spread = statistics.stdev(d.difference for d in curve.prompts)

        assert abs(curve.standard_error - spread / 6**0.5) < 1e-9
        assert curve.standard_error < spread / 2, "these are not the same number"


class TestTheCurveRefusesADifferentPromptSet:
    def test_two_runs_over_different_prompts(self, runner, rubric, brain, repo, generate):
        """Two runs covering different prompts are two measurements of
        different things — what the rubric pin prevents, on another axis.

        Constructed by reassigning one run's results rather than by calling
        `activate` twice, and that is worth knowing: `activate` only ever sets
        `active = 1`, and `summarize` measures completeness against the active
        set *now*. So changing the set retroactively marks every older run
        incomplete, and the incompleteness refusal fires before this one ever
        could. Both runs here stay complete, so this refusal is the one under
        test.
        """
        _seed_and_activate(runner, rubric, slugs=("a", "b"))
        first = runner.record_baseline(week_of="2026-08-31", rubric=rubric)
        runner.score(first, judge=_FixedJudge(GOOD), generate=generate, rubric=rubric)

        (Path(brain.path) / "profile.md").write_text("# Profile\n\nLater.\n")
        for args in (["add", "-A"], ["commit", "-q", "-m", "later"]):
            subprocess.run(["git", "-C", str(brain.path), *args], check=True, capture_output=True)

        second = runner.record_baseline(week_of="2026-10-19", rubric=rubric)
        runner.score(second, judge=_FixedJudge(GOOD), generate=generate, rubric=rubric)

        from secondshift.evals.content import PromptCandidate

        runner.load_candidates(
            [PromptCandidate(slug="c", label="c", prompt="prompt c")], rubric
        )
        moved_to = repo.connection.execute(
            "SELECT id FROM eval_prompts WHERE slug = 'c'"
        ).fetchone()["id"]
        was = repo.connection.execute(
            "SELECT id FROM eval_prompts WHERE slug = 'b'"
        ).fetchone()["id"]
        repo.connection.execute(
            "UPDATE eval_results SET eval_prompt_id = ? WHERE eval_run_id = ? "
            "AND eval_prompt_id = ?",
            (moved_to, second, was),
        )

        with pytest.raises(NotComparable, match="different prompts"):
            runner.curve(first, second)


class TestAScoreKnowsWhichModelProducedIt:
    """`eval_results.model_call_id` existed from the first migration and the
    `INSERT` never named it. What that cost is one row below: a week 1 generated
    locally and a week 8 generated in the cloud, reported as the brain learning."""

    def test_the_call_is_recorded_beside_the_score(self, runner, rubric, repo, generate):
        _seed_and_activate(runner, rubric)
        run_id = runner.record_baseline(week_of="2026-08-31", rubric=rubric)

        runner.score(run_id, judge=_FixedJudge(GOOD), generate=generate, rubric=rubric)

        rows = repo.connection.execute(
            "SELECT r.model_call_id AS call, c.model AS model FROM eval_results r "
            "JOIN model_calls c ON c.id = r.model_call_id WHERE r.eval_run_id = ?",
            (run_id,),
        ).fetchall()
        assert len(rows) == 6, "two prompts, three samples, every one joined to its call"
        assert {r["model"] for r in rows} == {"nemotron-3.5-lightning-30b"}

    def test_a_generator_that_returns_only_text_is_refused(self, runner, rubric):
        """Refused by name, and not caught as a failed sample.

        `score` swallows `RuntimeError` to record a bad output and continue, so a
        contract error raised as one would read as the model having produced
        nothing — six failures and an incomplete run, pointing at the model
        rather than at the caller.
        """
        _seed_and_activate(runner, rubric)
        run_id = runner.record_baseline(week_of="2026-08-31", rubric=rubric)

        with pytest.raises(TypeError, match="generate returned str"):
            runner.score(
                run_id,
                judge=_FixedJudge(GOOD),
                generate=lambda **kw: "an answer, with no call behind it",
                rubric=rubric,
            )

    def test_a_run_reports_what_produced_it(self, runner, rubric, generate):
        _seed_and_activate(runner, rubric)
        run_id = runner.record_baseline(week_of="2026-08-31", rubric=rubric)
        runner.score(run_id, judge=_FixedJudge(GOOD), generate=generate, rubric=rubric)

        summary = runner.summarize(run_id)

        assert summary.generators == ("local-vllm/nemotron-3.5-lightning-30b",)
        assert summary.generator_unrecorded is False

    def test_the_model_changing_between_runs_is_refused(
        self, runner, rubric, brain, generate, generate_in_the_cloud
    ):
        """The shortest path to a week-8 number, and the one that breaks it.

        Everything else about these two runs is comparable: same rubric, same
        judge, same prompts, two brain states, both complete. Only the generator
        differs, so this refusal is the one under test rather than one of the six
        that came before it.
        """
        _seed_and_activate(runner, rubric)
        first = runner.record_baseline(week_of="2026-08-31", rubric=rubric)
        runner.score(first, judge=_FixedJudge(GOOD), generate=generate, rubric=rubric)

        (Path(brain.path) / "profile.md").write_text("# Profile\n\nWeek eight belief.\n")
        for args in (["add", "-A"], ["commit", "-q", "-m", "week eight"]):
            subprocess.run(["git", "-C", str(brain.path), *args], check=True, capture_output=True)

        second = runner.record_baseline(week_of="2026-10-19", rubric=rubric)
        runner.score(
            second, judge=_FixedJudge(GOOD), generate=generate_in_the_cloud, rubric=rubric
        )

        with pytest.raises(NotComparable, match="different models produced the outputs"):
            runner.curve(first, second)

    def test_the_same_model_on_both_sides_compares(self, runner, rubric, brain, generate):
        """The other half, and the half that catches a refusal firing for the
        wrong reason. Two mutations survived on 23 Sep because the setup for a
        refusal satisfied a second condition at the same time."""
        _seed_and_activate(runner, rubric)
        first = runner.record_baseline(week_of="2026-08-31", rubric=rubric)
        runner.score(first, judge=_FixedJudge(GOOD), generate=generate, rubric=rubric)

        (Path(brain.path) / "profile.md").write_text("# Profile\n\nWeek eight belief.\n")
        for args in (["add", "-A"], ["commit", "-q", "-m", "week eight"]):
            subprocess.run(["git", "-C", str(brain.path), *args], check=True, capture_output=True)

        second = runner.record_baseline(week_of="2026-10-19", rubric=rubric)
        runner.score(
            second,
            judge=_FixedJudge({d: 5 for d in DIMENSIONS}),
            generate=generate,
            rubric=rubric,
        )

        curve = runner.curve(first, second)

        assert curve.difference > 0, "the same generator on both sides is comparable"

    def test_summarize_reports_what_produced_the_run(
        self, runner, rubric, tmp_path, capsys, generate
    ):
        """The judge was always printed here and the generator never was. That
        asymmetry is what let two models read as two states of one brain."""
        _seed_and_activate(runner, rubric)
        run_id = runner.record_baseline(week_of="2026-08-31", rubric=rubric)
        runner.score(run_id, judge=_FixedJudge(GOOD), generate=generate, rubric=rubric)

        code = main([
            "summarize", run_id,
            "--db", str(tmp_path / "second-shift.db"),
            "--rubric", str(rubric.path),
            "--brain", str(tmp_path / "brain"),
        ])

        assert code == 0
        assert "generated by local-vllm/nemotron-3.5-lightning-30b" in capsys.readouterr().out

    def test_an_unrecorded_generator_is_refused(
        self, runner, rubric, brain, repo, generate
    ):
        """A row written before the column was filled, which is every row the
        system would have had if this had been found after 15 Oct.

        Refused separately from the mismatch, and before it: "I cannot see what
        produced one side" is a different statement from "the two sides differ",
        and reporting the second here would name two models when one of them is
        not known.
        """
        _seed_and_activate(runner, rubric)
        first = runner.record_baseline(week_of="2026-08-31", rubric=rubric)
        runner.score(first, judge=_FixedJudge(GOOD), generate=generate, rubric=rubric)

        (Path(brain.path) / "profile.md").write_text("# Profile\n\nWeek eight belief.\n")
        for args in (["add", "-A"], ["commit", "-q", "-m", "week eight"]):
            subprocess.run(["git", "-C", str(brain.path), *args], check=True, capture_output=True)

        second = runner.record_baseline(week_of="2026-10-19", rubric=rubric)
        runner.score(second, judge=_FixedJudge(GOOD), generate=generate, rubric=rubric)
        repo.connection.execute(
            "UPDATE eval_results SET model_call_id = NULL WHERE eval_run_id = ?",
            (first,),
        )

        assert runner.summarize(first).generators == (UNRECORDED,)
        assert runner.summarize(first).generator_unrecorded is True
        with pytest.raises(NotComparable, match="name no model call"):
            runner.curve(first, second)


class TestTheJudgeIsAModel:
    """Until now nothing in this system had ever scored anything: `Judge` was a
    protocol with one implementation that returned arithmetic on the length of
    its input. The endpoint here is a real socket, so what is under test is the
    reading of a completion rather than a mock of it."""

    @pytest.fixture
    def judge(self, recorder, vllm_stub) -> ModelJudge:
        return ModelJudge(
            VllmReasoner(
                recorder,
                settings=LocalReasonerSettings(
                    host=vllm_stub.host,
                    port=vllm_stub.port,
                    model="stub-served-model",
                    max_tokens=256,
                    temperature=0.7,
                    timeout_s=5.0,
                ),
            ),
            policy="local-only",
            version="pinned-1",
        )

    def _scores(self, **overrides) -> str:
        scores = {d: 4 for d in DIMENSIONS}
        scores.update(overrides)
        return json.dumps({"scores": scores, "note": "fine"})

    def test_the_judge_reports_the_model_that_graded(self, judge):
        """Read from the provider at runtime, so it is the model that actually
        graded rather than what somebody wrote down — and so no model identifier
        lands outside the providers package."""
        assert judge.name == "stub-served-model"
        assert judge.version == "pinned-1"

    def test_a_bare_object_is_read(self, judge, vllm_stub, rubric):
        vllm_stub.answers(text=self._scores())

        judgement = judge.score(output="an answer", rubric=rubric.text, prompt="q")

        assert judgement.scores == {d: 4 for d in DIMENSIONS}
        assert judgement.note == "fine"

    def test_deliberation_before_the_object_is_ignored(self, judge, vllm_stub, rubric):
        """The served checkpoint emits its reasoning inconsistently — sometimes
        delimited, sometimes as bare prose, which `agents/invoke.py` records as
        the finding it is. Demanding a bare object would refuse every real
        completion."""
        vllm_stub.answers(
            text="Here's a thinking process: the answer interrogates well.\n"
            + self._scores(interrogation=5)
        )

        judgement = judge.score(output="an answer", rubric=rubric.text, prompt="q")

        assert judgement.scores["interrogation"] == 5

    def test_a_fenced_block_is_read(self, judge, vllm_stub, rubric):
        vllm_stub.answers(text=f"```json\n{self._scores(voice=2)}\n```")

        assert judge.score(output="a", rubric=rubric.text, prompt="q").scores["voice"] == 2

    def test_the_last_of_two_objects_is_the_judgement(self, judge, vllm_stub, rubric):
        """A model that restates its answer puts the final form last."""
        vllm_stub.answers(
            text=f"First pass: {self._scores(fit=1)}\nOn reflection: {self._scores(fit=5)}"
        )

        assert judge.score(output="a", rubric=rubric.text, prompt="q").scores["fit"] == 5

    def test_a_brace_inside_a_note_does_not_truncate_the_object(
        self, judge, vllm_stub, rubric
    ):
        """The note is the one field a model writes freely."""
        vllm_stub.answers(
            text=json.dumps(
                {"scores": {d: 3 for d in DIMENSIONS}, "note": "it wrote a } and a {"}
            )
        )

        judgement = judge.score(output="a", rubric=rubric.text, prompt="q")

        assert judgement.note == "it wrote a } and a {"
        assert judgement.total == 15

    def test_prose_with_no_object_is_refused(self, judge, vllm_stub, rubric):
        """Reading 4/5 out of a sentence would make the measurement depend on
        the model's formatting, which is what pinning the judge excludes."""
        vllm_stub.answers(text="Interrogation: 4/5. Fit: strong. Voice: 3 out of 5.")

        with pytest.raises(UnreadableJudgement, match="no JSON object"):
            judge.score(output="a", rubric=rubric.text, prompt="q")

    def test_a_truncated_completion_is_refused_before_it_is_parsed(
        self, judge, vllm_stub, rubric
    ):
        """The silent one. JSON cut off at a token limit can parse as a smaller
        valid object, so a judgement missing two dimensions would score on the
        rest. The object served here is valid and complete — only the stop
        reason says otherwise, which is the whole point: the refusal must not
        depend on the text happening to be broken too."""
        vllm_stub.answers(text=self._scores(), finish_reason="length")

        with pytest.raises(UnreadableJudgement, match="the judge stopped: length"):
            judge.score(output="a", rubric=rubric.text, prompt="q")

    def test_a_missing_dimension_is_refused(self, judge, vllm_stub, rubric):
        partial = {d: 4 for d in DIMENSIONS if d != "voice"}
        vllm_stub.answers(text=json.dumps({"scores": partial}))

        with pytest.raises(UnreadableJudgement, match="missing dimension 'voice'"):
            judge.score(output="a", rubric=rubric.text, prompt="q")

    def test_a_score_outside_the_range_is_refused(self, judge, vllm_stub, rubric):
        vllm_stub.answers(text=self._scores(fit=7))

        with pytest.raises(UnreadableJudgement, match="outside 1-5"):
            judge.score(output="a", rubric=rubric.text, prompt="q")

    def test_a_refused_judgement_still_recorded_its_call(
        self, judge, vllm_stub, rubric, repo
    ):
        """The case that matters for principle 7: a judge that failed to produce
        readable scores still cost tokens. The provider layer records before the
        judge reads, so the row exists whatever the text turned out to be."""
        vllm_stub.answers(text="no object at all")

        with pytest.raises(UnreadableJudgement):
            judge.score(output="a", rubric=rubric.text, prompt="q")

        rows = [dict(r) for r in repo.connection.execute("SELECT * FROM model_calls")]
        assert len(rows) == 1
        assert rows[0]["model"] == "stub-served-model"
        assert rows[0]["policy"] == "local-only"

    def test_the_rubric_and_the_answer_both_reach_the_model(
        self, judge, vllm_stub, rubric
    ):
        """A judge that did not send the rubric would grade against whatever it
        remembered, and the hash pinned to the run would be decorative."""
        vllm_stub.answers(text=self._scores())

        judge.score(output="the answer text", rubric=rubric.text, prompt="the question")

        sent = vllm_stub.requests[0]["messages"][0]["content"]
        assert rubric.text in sent
        assert "the answer text" in sent
        assert "the question" in sent

    # -- the three wrapper shapes the real checkpoint has been observed to
    # -- emit, on three different days. Invented shapes prove the extractor
    # -- survives my imagination; these prove it survives the model.

    def test_the_think_delimiter_shape(self, judge, vllm_stub, rubric):
        """`docs/MODELS.md`: the reasoning is wrapped in `<think>...</think>`
        inline in `content`, a structural delimiter rather than a prose marker,
        because no reasoning parser is configured on the server.

        The deliberation here carries braces, which is the part that matters: a
        scan that counted them outside string state would close the object early
        and parse a fragment.
        """
        vllm_stub.answers(
            text="<think>The rubric says {interrogation} first. I will weigh it "
            f"above voice.</think>\n{self._scores(interrogation=5)}"
        )

        judgement = judge.score(output="a", rubric=rubric.text, prompt="q")

        assert judgement.scores["interrogation"] == 5

    def test_the_bare_prose_shape(self, judge, vllm_stub, rubric):
        """`docs/SPEC_ROADMAP.md`: one live call opened with the literal
        `Here's a thinking process:` as prose, *not* inside the wrapper observed
        hours earlier the same day. The wrapper is inconsistent between calls,
        which is why the judge locates an object rather than stripping a
        delimiter — a strip conditioned on `</think>` handles one of these two
        and silently mangles the other.
        """
        vllm_stub.answers(
            text="Here's a thinking process: the answer is specific and asks "
            f"nothing back.\n\n{self._scores(interrogation=2)}"
        )

        judgement = judge.score(output="a", rubric=rubric.text, prompt="q")

        assert judgement.scores["interrogation"] == 2

    def test_an_unopened_close_delimiter(self, judge, vllm_stub, rubric):
        """The same observation's second half: "the strip trimmed something — a
        `</think>` did appear later". So a completion can carry a close with no
        open, which is the shape that breaks a delimiter-based split worst — it
        either deletes the answer or keeps all of the reasoning."""
        vllm_stub.answers(
            text=f"Weighing fit against actionability.</think>\n{self._scores(fit=1)}"
        )

        assert judge.score(output="a", rubric=rubric.text, prompt="q").scores["fit"] == 1

    def test_scores_drafted_in_the_reasoning_do_not_win(
        self, judge, vllm_stub, rubric
    ):
        """The realistic failure, and the reason the rule is *last* object.

        A model that shows its work drafts the scores, reconsiders, and restates
        them. Both drafts are valid JSON. Taking the first would record the
        number the model talked itself out of.
        """
        vllm_stub.answers(
            text="<think>First pass: "
            + self._scores(voice=1)
            + " — no, the voice is closer than that.</think>\n"
            + self._scores(voice=4)
        )

        assert judge.score(output="a", rubric=rubric.text, prompt="q").scores["voice"] == 4

    def test_a_run_scored_by_the_model_records_it_as_the_judge(
        self, runner, rubric, vllm_stub, judge, generate
    ):
        """End to end: the runner, the model judge and the curve's pinning all
        agree about which instrument graded the run."""
        vllm_stub.answers(text=self._scores())
        _seed_and_activate(runner, rubric)
        run_id = runner.record_baseline(week_of="2026-08-31", rubric=rubric)

        summary = runner.score(run_id, judge=judge, generate=generate, rubric=rubric)

        assert summary.judge_model == "stub-served-model"
        assert summary.complete is True
        assert summary.mean == 20.0, "five dimensions at four each"


class TestTheScoreCommand:
    """The command that did not exist until 10 Oct. `EvalRunner.score` was
    reachable only from this file, which meant the method producing the
    submission's number had no entry point an operator could run."""

    def _run(self, tmp_path, rubric, run_id, *extra) -> int:
        return main([
            "score", run_id, *extra,
            "--db", str(tmp_path / "second-shift.db"),
            "--rubric", str(rubric.path),
            "--brain", str(tmp_path / "brain"),
        ])

    @pytest.fixture
    def local(self, vllm_stub, monkeypatch):
        """A profile with local capability, pointed at the stub endpoint.

        The probe cannot find CUDA here, so without the override the command
        refuses — which is itself one of the tests below. `SECOND_SHIFT_PROFILE`
        is the documented override and the same one `config show` reports.
        """
        monkeypatch.setenv("SECOND_SHIFT_PROFILE", "workstation")
        monkeypatch.setenv("SECOND_SHIFT_LOCAL_HOST", vllm_stub.host)
        monkeypatch.setenv("SECOND_SHIFT_LOCAL_PORT", str(vllm_stub.port))
        monkeypatch.setenv("SECOND_SHIFT_LOCAL_MODEL", "stub-served-model")
        monkeypatch.setenv("SECOND_SHIFT_EMBEDDER_HOST", vllm_stub.host)
        monkeypatch.setenv("SECOND_SHIFT_EMBEDDER_PORT", str(vllm_stub.port))
        monkeypatch.setenv("SECOND_SHIFT_EMBEDDER_MODEL", "stub-embedder")
        return vllm_stub

    @pytest.fixture
    def baseline(self, runner, rubric) -> str:
        _seed_and_activate(runner, rubric)
        return runner.record_baseline(week_of="2026-08-31", rubric=rubric)

    def _scores(self) -> str:
        return json.dumps({"scores": {d: 4 for d in DIMENSIONS}, "note": "fine"})

    def test_a_run_is_generated_and_graded(
        self, local, baseline, runner, rubric, tmp_path, repo, capsys
    ):
        """One stub answers both the generation and the grading, so the answer
        under test is the judgement object itself. That is odd to read and
        correct for what is under test: whether the command reaches the runner,
        the agent path and the judge, and records what each one was."""
        local.answers(text=self._scores())

        code = self._run(tmp_path, rubric, baseline)

        assert code == 0
        out = capsys.readouterr().out
        assert "generated by local-vllm/stub-served-model" in out
        assert "prompt       architect.v1:" in out
        summary = runner.summarize(baseline)
        assert summary.judge_model == "stub-served-model"
        assert summary.complete is True

    def test_generation_goes_through_the_agent_path(
        self, local, baseline, rubric, tmp_path, repo
    ):
        """The answer is produced the way the product produces work. An answer
        from a composition written for evals would measure that composition."""
        local.answers(text=self._scores())

        self._run(tmp_path, rubric, baseline)

        rows = [dict(r) for r in repo.connection.execute(
            "SELECT DISTINCT a.role AS role FROM eval_results r "
            "JOIN model_calls c ON c.id = r.model_call_id "
            "JOIN agent_invocations i ON i.id = c.agent_invocation_id "
            "JOIN agents a ON a.id = i.agent_id WHERE r.eval_run_id = ?",
            (baseline,),
        )]
        assert [r["role"] for r in rows] == ["architect"]

    def test_the_brain_reaches_the_turn_as_context(
        self, local, baseline, rubric, tmp_path
    ):
        """Labeled by file, because the rubric scores voice and fit separately
        and a model that cannot tell the style guide from the profile cannot
        apply one without the other."""
        local.answers(text=self._scores())

        self._run(tmp_path, rubric, baseline)

        sent = "\n".join(
            m["content"] for m in local.requests[0]["messages"]
        )
        assert "--- profile.md ---" in sent
        assert "Week one belief." in sent
        assert "--- style-guide.md ---" in sent

    def test_no_local_reasoner_refuses(self, baseline, rubric, tmp_path, capsys):
        """Today's real answer in this container, and the one it must not dress
        up as a score. The registry binds an echo on `cloud`, and an echo's
        numbers are indistinguishable from a model's once recorded."""
        code = self._run(tmp_path, rubric, baseline)

        assert code == 2
        err = capsys.readouterr().err
        assert "no local reasoner can do the work" in err
        assert "fabricated numbers" in err

    def test_missing_configuration_refuses_and_writes_nothing(
        self, local, baseline, rubric, tmp_path, repo, capsys, monkeypatch
    ):
        """The settings live in `config/models.toml`, which has no path
        override, so the branch is reached by replacing the resolver the command
        imported. What is under test is the refusal, not the file reader."""
        from secondshift.config import EvalSettings
        import secondshift.evals.__main__ as entry

        monkeypatch.setattr(
            entry, "eval_settings", lambda: EvalSettings(judge_version="", role="")
        )

        code = self._run(tmp_path, rubric, baseline)

        assert code == 2
        assert "evals.judge_version and evals.generating_role" in capsys.readouterr().err
        rows = repo.connection.execute(
            "SELECT COUNT(*) AS n FROM eval_results"
        ).fetchone()
        assert rows["n"] == 0

    def test_a_judge_deployment_cannot_score_a_real_run(
        self, local, baseline, rubric, tmp_path, repo, capsys, monkeypatch
    ):
        """The hole the command made reachable. The flag marks results and the
        exclusion filters runs — two tables — so synthetic results under a real
        run read as that run's scores, and the 19 Sep exclusion never sees them."""
        monkeypatch.setenv("SECOND_SHIFT_SYNTHETIC", "1")
        local.answers(text=self._scores())

        code = self._run(tmp_path, rubric, baseline)

        assert code == 2
        assert "cannot score" in capsys.readouterr().err
        rows = repo.connection.execute(
            "SELECT COUNT(*) AS n FROM eval_results"
        ).fetchone()
        assert rows["n"] == 0


class TestAPromptEditedBetweenRunsIsNotLearning:
    """Generating through the product's agent path reintroduced the hole the
    generator refusal closed, one layer up: a role prompt is versioned, and
    `eval_runs` pins the brain, the rubric, the code and the judge but no
    prompt. `distiller` is already at v2, so this is not hypothetical."""

    def _generator(self, recorder, repo, vllm_stub, tmp_path, *, version: int):
        """A generator through `invoke`, at a chosen prompt version.

        The prompt directory is built here rather than reusing the shipped one,
        because the point is two runs whose prompts differ — and the shipped
        `architect` has exactly one version, which is the healthy case.
        """
        directory = tmp_path / f"prompts-v{version}"
        directory.mkdir()
        (directory / f"architect.v{version}.md").write_text(
            f"# Architect v{version}\n\nInterrogate the idea.\n"
        )
        agents = register(repo, directory=directory)
        prompt_file = discover(directory)["architect"]
        reasoner = VllmReasoner(
            recorder,
            settings=LocalReasonerSettings(
                host=vllm_stub.host, port=vllm_stub.port, model="stub-served-model",
                max_tokens=256, temperature=0.7, timeout_s=5.0,
            ),
        )

        def generate(*, prompt, brain, sample):
            turn = invoke(
                recorder,
                reasoner,
                role="architect",
                agent_id=agents["architect"],
                prompt_path=prompt_file.path,
                task=prompt,
                policy="local-only",
                context=brain.profile,
            )
            return Completion(
                text=turn.text,
                model_call_id=turn.model_call_id,
                prompt_tokens=8,
                completion_tokens=16,
            )

        return generate

    def _advance(self, brain, message: str) -> None:
        (Path(brain.path) / "profile.md").write_text(f"# Profile\n\n{message}\n")
        for args in (["add", "-A"], ["commit", "-q", "-m", message]):
            subprocess.run(
                ["git", "-C", str(brain.path), *args], check=True, capture_output=True
            )

    def test_a_run_reports_the_prompt_behind_it(
        self, runner, rubric, repo, recorder, vllm_stub, tmp_path
    ):
        vllm_stub.answers(text="an interrogation")
        _seed_and_activate(runner, rubric)
        run_id = runner.record_baseline(week_of="2026-08-31", rubric=rubric)

        runner.score(
            run_id,
            judge=_FixedJudge(GOOD),
            generate=self._generator(recorder, repo, vllm_stub, tmp_path, version=1),
            rubric=rubric,
        )

        versions = runner.summarize(run_id).prompt_versions
        assert len(versions) == 1
        assert versions[0].startswith("architect.v1:")

    def test_a_changed_prompt_version_is_refused(
        self, runner, rubric, repo, recorder, brain, vllm_stub, tmp_path
    ):
        """Everything else is comparable: same rubric, same judge, same prompts,
        same model, two brain states, both complete. Only the role prompt
        differs, so this refusal is the one under test rather than one of the
        nine before it."""
        vllm_stub.answers(text="an interrogation")
        _seed_and_activate(runner, rubric)
        first = runner.record_baseline(week_of="2026-08-31", rubric=rubric)
        runner.score(
            first,
            judge=_FixedJudge(GOOD),
            generate=self._generator(recorder, repo, vllm_stub, tmp_path, version=1),
            rubric=rubric,
        )

        self._advance(brain, "Week eight belief.")
        second = runner.record_baseline(week_of="2026-10-19", rubric=rubric)
        runner.score(
            second,
            judge=_FixedJudge(GOOD),
            generate=self._generator(recorder, repo, vllm_stub, tmp_path, version=2),
            rubric=rubric,
        )

        with pytest.raises(NotComparable, match="different agent prompts"):
            runner.curve(first, second)

    def test_the_same_prompt_on_both_sides_compares(
        self, runner, rubric, repo, recorder, brain, vllm_stub, tmp_path
    ):
        """The half that catches a refusal firing for the wrong reason."""
        vllm_stub.answers(text="an interrogation")
        _seed_and_activate(runner, rubric)
        generate = self._generator(recorder, repo, vllm_stub, tmp_path, version=1)

        first = runner.record_baseline(week_of="2026-08-31", rubric=rubric)
        runner.score(first, judge=_FixedJudge(GOOD), generate=generate, rubric=rubric)
        self._advance(brain, "Week eight belief.")
        second = runner.record_baseline(week_of="2026-10-19", rubric=rubric)
        runner.score(
            second,
            judge=_FixedJudge({d: 5 for d in DIMENSIONS}),
            generate=generate,
            rubric=rubric,
        )

        curve = runner.curve(first, second)

        assert curve.difference > 0

    def test_neither_run_using_an_agent_still_compares(
        self, runner, rubric, brain, generate
    ):
        """An absence shared by both sides is not a change between them. The
        non-agent shape is how every other test in this file generates, and
        refusing it would refuse them all."""
        _seed_and_activate(runner, rubric)
        first = runner.record_baseline(week_of="2026-08-31", rubric=rubric)
        runner.score(first, judge=_FixedJudge(GOOD), generate=generate, rubric=rubric)
        self._advance(brain, "Week eight belief.")
        second = runner.record_baseline(week_of="2026-10-19", rubric=rubric)
        runner.score(
            second,
            judge=_FixedJudge({d: 5 for d in DIMENSIONS}),
            generate=generate,
            rubric=rubric,
        )

        assert runner.summarize(first).prompt_versions == (UNRECORDED,)
        assert runner.curve(first, second).difference > 0
