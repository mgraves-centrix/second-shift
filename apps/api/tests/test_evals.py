"""The measurement spine: sampling, pinning, and scoring against a recorded brain."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from secondshift.brain.repo import BrainRepo, BrainUnavailable
from secondshift.evals.content import Rubric, load_prompts, load_rubric
from secondshift.evals.judge import (
    DIMENSIONS,
    Judgement,
    StubJudge,
    UnreadableJudgement,
)
from secondshift.evals.runner import AWAITING, EvalRunner, NoJudgeConfigured

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


def _generate(prompt: str, brain, sample: int) -> str:
    return f"{prompt} answered from: {brain.profile.strip()[:20]} #{sample}"


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
        self, runner, rubric, repo, brain
    ):
        _seed_and_activate(runner, rubric)
        run_id = runner.record_baseline(week_of="2026-08-24", rubric=rubric)
        baseline_sha = brain.head()
        (brain.path / "profile.md").write_text("# Profile\n\nlater\n")
        subprocess.run(["git", "-C", str(brain.path), "commit", "-qam", "later"],
                       check=True, capture_output=True)

        runner.score(run_id, judge=StubJudge(), generate=_generate, rubric=rubric)
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
    def test_three_samples_per_prompt(self, runner, rubric, repo):
        _seed_and_activate(runner, rubric)
        run_id = runner.record_baseline(week_of="2026-08-24", rubric=rubric)
        runner.score(run_id, judge=StubJudge(), generate=_generate, rubric=rubric)
        rows = repo.connection.execute(
            "SELECT eval_prompt_id, sample_index FROM eval_results WHERE eval_run_id = ?",
            (run_id,),
        ).fetchall()
        assert len(rows) == 6
        assert sorted({r["sample_index"] for r in rows}) == [0, 1, 2]

    def test_summary_reports_a_center_and_a_spread(self, runner, rubric):
        _seed_and_activate(runner, rubric)
        run_id = runner.record_baseline(week_of="2026-08-24", rubric=rubric)
        summary = runner.score(run_id, judge=StubJudge(), generate=_generate, rubric=rubric)
        assert len(summary.prompts) == 2
        for prompt in summary.prompts:
            assert len(prompt.samples) == 3
            assert prompt.mean > 0
            assert prompt.spread >= 0
        assert summary.complete is True

    def test_pinning_is_recorded_on_the_run(self, runner, rubric, repo):
        _seed_and_activate(runner, rubric)
        run_id = runner.record_baseline(week_of="2026-08-24", rubric=rubric)
        judge = StubJudge()
        runner.score(run_id, judge=judge, generate=_generate, rubric=rubric)
        row = repo.connection.execute(
            "SELECT judge_model, judge_model_version, rubric_sha FROM eval_runs WHERE id = ?",
            (run_id,),
        ).fetchone()
        assert row["judge_model"] == judge.name
        assert row["judge_model_version"] == judge.version
        assert row["rubric_sha"] == rubric.sha

    def test_subscores_are_recorded_per_dimension(self, runner, rubric, repo):
        _seed_and_activate(runner, rubric)
        run_id = runner.record_baseline(week_of="2026-08-24", rubric=rubric)
        runner.score(run_id, judge=StubJudge(), generate=_generate, rubric=rubric)
        row = repo.connection.execute(
            "SELECT subscores_json FROM eval_results WHERE eval_run_id = ? LIMIT 1",
            (run_id,),
        ).fetchone()
        assert set(json.loads(row["subscores_json"])) == set(DIMENSIONS)


class TestFailureHandling:
    def test_no_judge_configured_refuses(self, runner, rubric):
        _seed_and_activate(runner, rubric)
        run_id = runner.record_baseline(week_of="2026-08-24", rubric=rubric)
        with pytest.raises(NoJudgeConfigured, match="refusing"):
            runner.score(run_id, judge=None, generate=_generate, rubric=rubric)

    def test_an_unreadable_judgement_records_a_failure_not_a_zero(
        self, runner, rubric, repo
    ):
        class Broken(StubJudge):
            def score(self, *, output, rubric, prompt):
                raise UnreadableJudgement("returned prose")

        _seed_and_activate(runner, rubric, slugs=("a",))
        run_id = runner.record_baseline(week_of="2026-08-24", rubric=rubric)
        summary = runner.score(run_id, judge=Broken(), generate=_generate, rubric=rubric)

        assert summary.prompts == []
        assert summary.complete is False
        failures = repo.connection.execute(
            "SELECT type, message FROM failures"
        ).fetchall()
        assert len(failures) == 3
        assert all(f["type"] == "bad_output" for f in failures)

    def test_a_partial_run_records_its_successes(self, runner, rubric):
        calls = {"n": 0}

        class Flaky(StubJudge):
            def score(self, *, output, rubric, prompt):
                calls["n"] += 1
                if calls["n"] == 2:
                    raise UnreadableJudgement("one bad sample")
                return Judgement(scores=GOOD)

        _seed_and_activate(runner, rubric, slugs=("a",))
        run_id = runner.record_baseline(week_of="2026-08-24", rubric=rubric)
        summary = runner.score(run_id, judge=Flaky(), generate=_generate, rubric=rubric)

        assert summary.prompts[0].samples == [20, 20]
        assert summary.complete is False

    def test_an_incomplete_run_is_evident(self, runner, rubric):
        _seed_and_activate(runner, rubric)
        run_id = runner.record_baseline(week_of="2026-08-24", rubric=rubric)
        assert runner.summarize(run_id).complete is False
