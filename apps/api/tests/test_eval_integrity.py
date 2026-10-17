"""What the first real scoring on the always-on machine found, held in place.

On 16 Oct a week-8 run lost two of its first five samples to judgements the
parser refused, and three things about the instrument turned out to be wrong
beyond the refusals themselves:

- a refused judgement could not be read back, because nothing kept its text,
  and its failure row did not say which call produced it;
- a run that lost one sample could never be completed, and a second `score`
  crashed on the first already-recorded sample instead of refusing;
- the judge's own prompt was pinned by nothing, so a fix to it would have
  changed the instrument between two runs the curve still called comparable.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from secondshift.brain.repo import BrainRepo
from secondshift.evals.__main__ import main
from secondshift.evals.content import PromptCandidate, Rubric, load_rubric
from secondshift.evals.judge import _ASK, ASK_SHA, DIMENSIONS, Judgement, ModelJudge
from secondshift.evals.runner import AlreadyScored, EvalRunner, NotComparable
from secondshift.providers.base import Message, RawCompletion, Reasoner

GOOD = json.dumps({"scores": {d: 4 for d in DIMENSIONS}, "note": "fine"})


@pytest.fixture
def brain(tmp_path) -> BrainRepo:
    path = tmp_path / "brain"
    (path / "skills").mkdir(parents=True)
    (path / "profile.md").write_text("# Profile\n\nWeek one.\n")
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
    path.write_text("# Rubric\n\nFive dimensions.\n")
    return load_rubric(path)


@pytest.fixture
def runner(repo, brain, rubric) -> EvalRunner:
    runner = EvalRunner(repo, brain=brain, samples=1)
    runner.load_candidates([PromptCandidate(slug="a", label="a", prompt="prompt a")], rubric)
    runner.activate(["a"])
    return runner


class _Scripted(Reasoner):
    """Answers from a script, in order, through the real `complete`."""

    provider_kind = "local-vllm"

    def __init__(self, recorder, answers):
        super().__init__(recorder, model="scripted")
        self._answers = list(answers)

    def _do_complete(self, messages, *, effort):
        return RawCompletion(text=self._answers.pop(0), prompt_tokens=3, completion_tokens=3)


def _generate_through(reasoner):
    def generate(*, prompt, brain, sample):
        return reasoner.complete([Message("user", prompt)], policy="local-only")

    return generate


class _Fixed:
    name = "fixed"

    def __init__(self, version="1"):
        self.version = version

    def score(self, *, output, rubric, prompt):
        return Judgement({d: 4 for d in DIMENSIONS})


class TestAResultPointsAtTheTextItScored:
    def test_the_output_path_is_the_generation_s_kept_completion(
        self, runner, rubric, recorder, repo
    ):
        reasoner = _Scripted(recorder, ["an answer"])
        run = runner.record_baseline(week_of="w", rubric=rubric)

        runner.score(run, judge=_Fixed(), generate=_generate_through(reasoner), rubric=rubric)

        result = repo.connection.execute(
            "SELECT model_call_id, output_path FROM eval_results WHERE eval_run_id = ?",
            (run,),
        ).fetchone()
        assert result["output_path"] == repo.payload_for(result["model_call_id"])["completion_path"]


class TestARefusedJudgementCanBeReadBack:
    def test_the_failure_names_the_judge_call_and_the_answer_it_judged(
        self, runner, rubric, recorder, repo
    ):
        """The refusal stays a refusal. What changes is that somebody can now
        open the exact text the parser refused."""
        generator = _Scripted(recorder, ["an answer"])
        judge = ModelJudge(
            _Scripted(recorder, ['{"scores": {"interrogation": <1-5>}}']),
            policy="local-only",
            version="pinned",
        )
        run = runner.record_baseline(week_of="w", rubric=rubric)

        summary = runner.score(run, judge=judge, generate=_generate_through(generator), rubric=rubric)

        assert summary.complete is False
        failure = repo.connection.execute(
            "SELECT signature, context_json FROM failures WHERE signature LIKE 'eval:%'"
        ).fetchone()
        context = json.loads(failure["context_json"])
        assert repo.payload_for(context["judge_model_call_id"]) is not None
        assert repo.payload_for(context["answer_model_call_id"]) is not None


class TestARunIsScoredOnce:
    def test_a_scored_run_is_refused_rather_than_crashing(self, runner, rubric, recorder, repo):
        run = runner.record_baseline(week_of="w", rubric=rubric)
        runner.score(run, judge=_Fixed(), generate=_generate_through(_Scripted(recorder, ["x"])), rubric=rubric)

        with pytest.raises(AlreadyScored, match="new baseline"):
            runner.score(run, judge=_Fixed(), generate=_generate_through(_Scripted(recorder, ["y"])), rubric=rubric)

        count = repo.connection.execute(
            "SELECT COUNT(*) FROM eval_results WHERE eval_run_id = ?", (run,)
        ).fetchone()[0]
        assert count == 1

    def test_an_interrupted_run_is_refused_before_anything_is_generated(
        self, runner, rubric, recorder, repo
    ):
        """The shape a killed process leaves: results recorded, the judge never
        written back. It reads as awaiting scoring, and scoring it crashed on
        `UNIQUE(eval_run_id, eval_prompt_id, sample_index)`."""
        run = runner.record_baseline(week_of="w", rubric=rubric)
        runner.score(run, judge=_Fixed(), generate=_generate_through(_Scripted(recorder, ["x"])), rubric=rubric)
        repo.connection.execute(
            "UPDATE eval_runs SET judge_model = 'awaiting-scoring', ended_at_ms = NULL WHERE id = ?",
            (run,),
        )
        generator = _Scripted(recorder, [])

        with pytest.raises(AlreadyScored):
            runner.score(run, judge=_Fixed(), generate=_generate_through(generator), rubric=rubric)

    def test_status_says_an_interrupted_run_cannot_be_scored(
        self, runner, rubric, recorder, repo, tmp_path, brain, capsys, conn
    ):
        run = runner.record_baseline(week_of="w", rubric=rubric)
        runner.score(run, judge=_Fixed(), generate=_generate_through(_Scripted(recorder, ["x"])), rubric=rubric)
        repo.connection.execute(
            "UPDATE eval_runs SET judge_model = 'awaiting-scoring' WHERE id = ?", (run,)
        )
        conn.commit()

        main(["status", "--db", str(tmp_path / "second-shift.db"),
              "--brain", str(brain.path), "--rubric", str(rubric.path)])

        line = next(l for l in capsys.readouterr().out.splitlines() if run in l)
        assert "interrupted" in line and "awaiting scoring" not in line


class TestTheJudgeIsPinnedByWhatItAsks:
    def test_the_version_carries_the_hash_of_the_ask(self, recorder):
        judge = ModelJudge(_Scripted(recorder, []), policy="local-only", version="pinned")

        assert ASK_SHA == hashlib.sha256(_ASK.encode()).hexdigest()
        assert judge.version == f"pinned/ask:{ASK_SHA[:12]}"

    def test_a_scored_run_records_it(self, runner, rubric, recorder, repo):
        judge = ModelJudge(_Scripted(recorder, [GOOD]), policy="local-only", version="pinned")
        run = runner.record_baseline(week_of="w", rubric=rubric)

        runner.score(run, judge=judge, generate=_generate_through(_Scripted(recorder, ["x"])), rubric=rubric)

        recorded = repo.connection.execute(
            "SELECT judge_model_version FROM eval_runs WHERE id = ?", (run,)
        ).fetchone()[0]
        assert recorded == f"pinned/ask:{ASK_SHA[:12]}"

    def test_the_curve_refuses_one_judge_asking_two_ways(self, runner, rubric, recorder, brain):
        """Same model, same name, a different ask: two instruments. The curve
        compared judges by name alone, so this passed every refusal it had."""
        first = runner.record_baseline(week_of="w1", rubric=rubric)
        runner.score(first, judge=_Fixed("1/ask:aaaaaaaaaaaa"),
                     generate=_generate_through(_Scripted(recorder, ["x"])), rubric=rubric)
        (Path(brain.path) / "profile.md").write_text("# Profile\n\nWeek eight.\n")
        for args in (["add", "-A"], ["commit", "-q", "-m", "week eight"]):
            subprocess.run(["git", "-C", str(brain.path), *args], check=True, capture_output=True)
        second = runner.record_baseline(week_of="w8", rubric=rubric)
        runner.score(second, judge=_Fixed("1/ask:bbbbbbbbbbbb"),
                     generate=_generate_through(_Scripted(recorder, ["y"])), rubric=rubric)

        with pytest.raises(NotComparable, match="different judge versions"):
            runner.curve(first, second)


class TestTheCommandFindsItsContentFromAnywhere:
    def test_status_runs_outside_the_repository(self, tmp_path, monkeypatch, brain, capsys):
        """`config/evals/rubric.md` resolved against the working directory, so
        on the machine, over SSH, `status` died with a traceback naming a
        relative path. The content ships beside the code in both a clone and
        the deployed tree, so that is where it is looked for."""
        monkeypatch.chdir(tmp_path)

        code = main(["status", "--db", str(tmp_path / "elsewhere.db"), "--brain", str(brain.path)])

        assert code == 0
        assert "rubric on disk" in capsys.readouterr().out
