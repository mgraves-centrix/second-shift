"""The measurement spine: sampling, pinning, and scoring against a recorded brain."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from secondshift.brain.repo import BrainRepo, BrainUnavailable
from secondshift.evals.__main__ import main
from secondshift.evals.content import Rubric, load_prompts, load_rubric, load_threshold
from secondshift.evals.judge import (
    DIMENSIONS,
    Judgement,
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
)

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

    def test_scoring_under_a_different_rubric_is_refused(self, runner, rubric, tmp_path):
        _seed_and_activate(runner, rubric)
        run_id = runner.record_baseline(week_of="2026-08-24", rubric=rubric)
        drifted = self._drifted(tmp_path)

        with pytest.raises(RubricMismatch) as raised:
            runner.score(run_id, judge=StubJudge(), generate=_generate, rubric=drifted)

        # Both hashes named: a refusal that does not say which two values
        # disagree leaves the operator running the same SQL by hand.
        message = str(raised.value)
        assert rubric.sha[:12] in message
        assert drifted.sha[:12] in message

    def test_a_refused_score_records_nothing(self, runner, rubric, repo, tmp_path):
        _seed_and_activate(runner, rubric)
        run_id = runner.record_baseline(week_of="2026-08-24", rubric=rubric)

        with pytest.raises(RubricMismatch):
            runner.score(
                run_id, judge=StubJudge(), generate=_generate,
                rubric=self._drifted(tmp_path),
            )

        assert repo.connection.execute(
            "SELECT COUNT(*) n FROM eval_results WHERE eval_run_id = ?", (run_id,)
        ).fetchone()["n"] == 0
        assert runner.awaiting_scoring() == [run_id]

    def test_a_refusal_is_not_recorded_as_failed_samples(
        self, runner, rubric, repo, tmp_path
    ):
        """A wrong rubric is wrong for every sample, so it is not a partial run."""
        _seed_and_activate(runner, rubric)
        run_id = runner.record_baseline(week_of="2026-08-24", rubric=rubric)
        before = repo.connection.execute("SELECT COUNT(*) n FROM failures").fetchone()["n"]

        with pytest.raises(RubricMismatch):
            runner.score(
                run_id, judge=StubJudge(), generate=_generate,
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

    def test_scoring_under_the_pinned_rubric_proceeds(self, runner, rubric, repo):
        _seed_and_activate(runner, rubric)
        run_id = runner.record_baseline(week_of="2026-08-24", rubric=rubric)
        summary = runner.score(run_id, judge=StubJudge(), generate=_generate, rubric=rubric)
        assert summary.complete
        assert repo.connection.execute(
            "SELECT COUNT(*) n FROM eval_results WHERE eval_run_id = ?", (run_id,)
        ).fetchone()["n"] == 6

    def test_an_identical_rubric_at_another_path_is_the_same_rubric(
        self, runner, rubric, tmp_path
    ):
        """The hash follows content, not location. A copy is not drift."""
        elsewhere = tmp_path / "copied" / "rubric.md"
        elsewhere.parent.mkdir()
        elsewhere.write_text(rubric.text)

        _seed_and_activate(runner, rubric)
        run_id = runner.record_baseline(week_of="2026-08-24", rubric=rubric)
        summary = runner.score(
            run_id, judge=StubJudge(), generate=_generate, rubric=load_rubric(elsewhere)
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
        self, runner, rubric, tmp_path, capsys
    ):
        _seed_and_activate(runner, rubric)
        run_id = runner.record_baseline(week_of="2026-08-24", rubric=rubric)
        runner.score(run_id, judge=StubJudge(), generate=_generate, rubric=rubric)

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
    def two_runs(self, runner, rubric, brain):
        """Two scored runs over two brain states, which is the only shape that
        is actually comparable."""
        _seed_and_activate(runner, rubric)
        first = runner.record_baseline(week_of="2026-08-31", rubric=rubric)
        runner.score(first, judge=_FixedJudge(GOOD), generate=_generate, rubric=rubric)

        (Path(brain.path) / "profile.md").write_text("# Profile\n\nWeek eight belief.\n")
        for args in (["add", "-A"], ["commit", "-q", "-m", "week eight"]):
            subprocess.run(["git", "-C", str(brain.path), *args], check=True, capture_output=True)

        second = runner.record_baseline(week_of="2026-10-19", rubric=rubric)
        runner.score(second, judge=_FixedJudge({d: 5 for d in DIMENSIONS}), generate=_generate, rubric=rubric)
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

    def test_a_difference_inside_the_noise_is_not_a_change(self, runner, rubric, brain):
        """A real difference, and still not a change.

        The first draft of this test used two judges whose means were exactly
        equal, so `moved` was False for the wrong reason — replacing the spread
        comparison with `difference != 0` left it green. A test for "inside the
        noise" needs a difference that is not zero.
        """
        _seed_and_activate(runner, rubric)
        first = runner.record_baseline(week_of="2026-08-31", rubric=rubric)
        runner.score(first, judge=_VaryingJudge([1, 5, 3]), generate=_generate, rubric=rubric)

        (Path(brain.path) / "profile.md").write_text("# Profile\n\nLater.\n")
        for args in (["add", "-A"], ["commit", "-q", "-m", "later"]):
            subprocess.run(["git", "-C", str(brain.path), *args], check=True, capture_output=True)
        second = runner.record_baseline(week_of="2026-10-19", rubric=rubric)
        runner.score(second, judge=_VaryingJudge([3, 4, 3]), generate=_generate, rubric=rubric)

        curve = runner.curve(first, second)

        assert curve.difference != 0, "a zero difference would prove nothing here"
        assert abs(curve.difference) < curve.spread
        assert curve.moved is False

    def test_the_same_brain_is_refused(self, runner, rubric):
        """The one most likely to happen by accident: run the week-8 eval
        without the brain having moved, and the curve reports sampling noise."""
        _seed_and_activate(runner, rubric)
        first = runner.record_baseline(week_of="2026-08-31", rubric=rubric)
        runner.score(first, judge=_FixedJudge(GOOD), generate=_generate, rubric=rubric)
        second = runner.record_baseline(week_of="2026-10-19", rubric=rubric)
        runner.score(second, judge=_FixedJudge(GOOD), generate=_generate, rubric=rubric)

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

    def test_a_regression_hidden_by_the_mean_is_visible(self, runner, rubric, brain):
        """The case the per-dimension breakdown exists for, and the one that will
        not occur by accident in a fixture: the overall mean improves while one
        dimension goes backwards."""
        _seed_and_activate(runner, rubric)
        first = runner.record_baseline(week_of="2026-08-31", rubric=rubric)
        runner.score(
            first,
            judge=_FixedJudge({**{d: 3 for d in DIMENSIONS}, "voice": 5}),
            generate=_generate,
            rubric=rubric,
        )

        (Path(brain.path) / "profile.md").write_text("# Profile\n\nLouder.\n")
        for args in (["add", "-A"], ["commit", "-q", "-m", "louder"]):
            subprocess.run(["git", "-C", str(brain.path), *args], check=True, capture_output=True)
        second = runner.record_baseline(week_of="2026-10-19", rubric=rubric)
        runner.score(
            second,
            judge=_FixedJudge({**{d: 5 for d in DIMENSIONS}, "voice": 1}),
            generate=_generate,
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

    def test_one_scored_run_is_still_not_a_curve(self, runner, rubric, tmp_path, capsys):
        _seed_and_activate(runner, rubric)
        run_id = runner.record_baseline(week_of="2026-08-31", rubric=rubric)
        runner.score(run_id, judge=StubJudge(), generate=_generate, rubric=rubric)

        code = self._run(tmp_path, rubric.path)

        assert code == 1
        assert "1 scored run" in capsys.readouterr().err

    def test_a_refusal_is_reported_on_stderr_and_exits_non_zero(
        self, runner, rubric, tmp_path, capsys
    ):
        _seed_and_activate(runner, rubric)
        first = runner.record_baseline(week_of="2026-08-31", rubric=rubric)
        runner.score(first, judge=StubJudge(), generate=_generate, rubric=rubric)
        second = runner.record_baseline(week_of="2026-10-19", rubric=rubric)
        runner.score(second, judge=StubJudge(), generate=_generate, rubric=rubric)

        code = self._run(tmp_path, rubric.path)

        assert code == 1
        assert "brain did not change" in capsys.readouterr().err

    def test_a_comparison_prints_the_spread_beside_the_difference(
        self, runner, rubric, brain, tmp_path, capsys
    ):
        """There is no output shape that shows a difference without its spread."""
        _seed_and_activate(runner, rubric)
        first = runner.record_baseline(week_of="2026-08-31", rubric=rubric)
        runner.score(first, judge=_FixedJudge({d: 3 for d in DIMENSIONS}),
                     generate=_generate, rubric=rubric)
        (Path(brain.path) / "profile.md").write_text("# Profile\n\nLater.\n")
        for args in (["add", "-A"], ["commit", "-q", "-m", "later"]):
            subprocess.run(["git", "-C", str(brain.path), *args], check=True, capture_output=True)
        second = runner.record_baseline(week_of="2026-10-19", rubric=rubric)
        runner.score(second, judge=_FixedJudge({d: 5 for d in DIMENSIONS}),
                     generate=_generate, rubric=rubric)

        code = self._run(tmp_path, rubric.path)
        out = capsys.readouterr().out

        assert code == 0
        assert "difference" in out and "spread" in out
        assert "dimensions moved the same way" in out
        for dimension in DIMENSIONS:
            assert dimension in out

    def test_two_identifiers_are_taken_in_order(self, runner, rubric, tmp_path, capsys):
        """A wrong pair compared by hand is the failure the no-argument form avoids."""
        _seed_and_activate(runner, rubric)
        first = runner.record_baseline(week_of="2026-08-31", rubric=rubric)
        runner.score(first, judge=StubJudge(), generate=_generate, rubric=rubric)

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
    def test_two_runs_over_different_prompts(self, runner, rubric, brain, repo):
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
        runner.score(first, judge=_FixedJudge(GOOD), generate=_generate, rubric=rubric)

        (Path(brain.path) / "profile.md").write_text("# Profile\n\nLater.\n")
        for args in (["add", "-A"], ["commit", "-q", "-m", "later"]):
            subprocess.run(["git", "-C", str(brain.path), *args], check=True, capture_output=True)

        second = runner.record_baseline(week_of="2026-10-19", rubric=rubric)
        runner.score(second, judge=_FixedJudge(GOOD), generate=_generate, rubric=rubric)

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
