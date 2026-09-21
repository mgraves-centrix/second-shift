"""Running and scoring an eval set.

Two operations, deliberately separable. `record_baseline` fixes the inputs when
no model may yet exist — the prompts, the rubric hash, and the brain commit.
`score` produces outputs and grades them later, reading the brain **at the
recorded commit**.

That separation is the whole reason this is not one function. A week-1 baseline
recorded before any model was available must still be a week-1 measurement when
it is scored on day 5, and it only is if the generation reads the brain the
baseline pinned rather than the one on disk.
"""

from __future__ import annotations

import json
import statistics
from dataclasses import dataclass, field

from ..brain.repo import BrainRepo, BrainUnavailable
from ..db.connection import now_ms
from ..db.ids import new_ulid
from ..db.repository import Repository
from ..telemetry.failures import BadOutput
from .content import PromptCandidate, Rubric
from .judge import DIMENSIONS, Judge, Judgement, UnreadableJudgement

#: A run with no judge recorded has inputs but no scores. Stored in the judge
#: column rather than a status column: the absence *is* the state, and a
#: separate flag could disagree with it.
AWAITING = "awaiting-scoring"


class NoJudgeConfigured(RuntimeError):
    """Scoring was attempted with nothing to score with."""


class NotComparable(RuntimeError):
    """Two runs that cannot be compared without the answer meaning something else.

    Raised rather than warned. A warning on a report that ends up in a
    submission is a warning nobody sees, and every condition that raises this
    changes what the reported number is a measurement *of*.
    """


class RubricMismatch(RuntimeError):
    """Scoring was attempted under a rubric the run did not pin.

    Raised before generation rather than recorded per sample. A failed sample is
    evidence about one output; a wrong rubric is wrong for every sample in the
    same way, so recording it as a partial run would present a rubric error as a
    measurement of the brain.
    """


@dataclass(frozen=True, slots=True)
class PromptSummary:
    slug: str
    samples: list[int]

    @property
    def mean(self) -> float:
        return statistics.fmean(self.samples) if self.samples else 0.0

    @property
    def spread(self) -> float:
        """Standard deviation, or zero below two samples.

        Reported alongside the mean because a single sample cannot distinguish
        improvement from variance, and a difference without a spread is not
        evidence.
        """
        return statistics.stdev(self.samples) if len(self.samples) > 1 else 0.0


@dataclass(frozen=True, slots=True)
class DimensionDelta:
    """One rubric dimension across two runs.

    Carried because an overall mean that moved by 0.4 could be five dimensions
    improving slightly or `interrogation` improving substantially while `voice`
    regresses — and for a product whose thesis is that the brain learned this
    person's judgement, the second is the finding.
    """

    dimension: str
    earlier: float
    later: float

    @property
    def difference(self) -> float:
        return self.later - self.earlier


@dataclass(frozen=True, slots=True)
class Curve:
    """Two runs, and whether the difference between them survives the noise."""

    earlier: RunSummary
    later: RunSummary
    dimensions: list[DimensionDelta]

    @property
    def difference(self) -> float:
        return self.later.mean - self.earlier.mean

    @property
    def spread(self) -> float:
        """The wider of the two runs', which is what the difference must clear."""
        return max(_spread_of(self.earlier), _spread_of(self.later))

    @property
    def moved(self) -> bool:
        """Whether the difference is larger than the sampling spread.

        Not a significance test. Six prompts and a handful of samples make a
        t-test arithmetic dressed as rigor; this is a statement a reader can
        check by eye, and it does not imply a p-value nobody computed.
        """
        return abs(self.difference) > self.spread

    @property
    def agreeing_dimensions(self) -> int:
        """How many dimensions moved the same way the overall mean did.

        An overall mean can be carried by one dimension. A claim about the whole
        rubric needs more than one of its five to agree.
        """
        if self.difference == 0:
            return 0
        sign = 1 if self.difference > 0 else -1
        return sum(1 for d in self.dimensions if d.difference * sign > 0)


def _spread_of(summary: RunSummary) -> float:
    values = [s for p in summary.prompts for s in p.samples]
    return statistics.stdev(values) if len(values) > 1 else 0.0


@dataclass(frozen=True, slots=True)
class RecordedRun:
    """A run as it was pinned, independent of whether it has been scored."""

    eval_run_id: str
    week_of: str
    rubric_sha: str
    brain_sha: str
    judge_model: str

    @property
    def awaiting(self) -> bool:
        return self.judge_model == AWAITING


@dataclass(frozen=True, slots=True)
class RunSummary:
    eval_run_id: str
    brain_sha: str | None
    rubric_sha: str
    judge_model: str
    complete: bool
    prompts: list[PromptSummary] = field(default_factory=list)

    @property
    def mean(self) -> float:
        values = [s for p in self.prompts for s in p.samples]
        return statistics.fmean(values) if values else 0.0


class EvalRunner:
    def __init__(
        self,
        repo: Repository,
        *,
        brain: BrainRepo | None = None,
        samples: int = 3,
        is_synthetic: bool = False,
    ) -> None:
        """
        `is_synthetic` marks everything this runner writes, and is the
        deployment's own determination rather than an argument a caller picks:
        `__main__` reads it from `synthetic_flag()`, the same server-derived
        route capture already takes.

        It defaults to False because every row written before 19 Sep was written
        on the personal instance, and the eval tables carried no such column at
        all until then — so an evaluation run on a judge deployment wrote
        unmarked rows into the curve the whole submission rests on.
        """
        self._repo = repo
        self._brain = brain if brain is not None else BrainRepo()
        self._samples = samples
        self._is_synthetic = is_synthetic

    # -- content -----------------------------------------------------------

    def load_candidates(self, candidates: list[PromptCandidate], rubric: Rubric) -> int:
        """Record candidates as inactive. Selection is marking them active.

        Narrowing ten to five must not delete five: the unselected ones are the
        reserve, and a set chosen by deletion cannot be revisited.
        """
        added = 0
        for candidate in candidates:
            existing = self._repo.connection.execute(
                "SELECT id FROM eval_prompts WHERE slug = ?", (candidate.slug,)
            ).fetchone()
            if existing:
                continue
            self._repo.connection.execute(
                "INSERT INTO eval_prompts (id, slug, prompt, rubric_path, rubric_sha, "
                "created_at_ms, active, is_synthetic) VALUES (?, ?, ?, ?, ?, ?, 0, ?)",
                (new_ulid(now_ms()), candidate.slug, candidate.prompt,
                 str(rubric.path), rubric.sha, now_ms(), int(self._is_synthetic)),
            )
            added += 1
        return added

    def activate(self, slugs: list[str]) -> int:
        cursor = self._repo.connection.execute(
            f"UPDATE eval_prompts SET active = 1 WHERE slug IN "
            f"({','.join('?' * len(slugs))})",
            slugs,
        )
        return cursor.rowcount

    def active_prompts(self) -> list[tuple[str, str, str]]:
        return [
            (r["id"], r["slug"], r["prompt"])
            for r in self._repo.connection.execute(
                "SELECT id, slug, prompt FROM eval_prompts WHERE active = 1 ORDER BY slug"
            )
        ]

    # -- running -----------------------------------------------------------

    def record_baseline(self, *, week_of: str, rubric: Rubric, code_sha: str = "") -> str:
        """Fix the inputs, before any model exists to score them.

        Records what cannot be reconstructed later: which prompts, which rubric,
        and which brain. The judge is deliberately absent, which is what marks
        the run as awaiting scoring.
        """
        # The schema requires a brain commit, and rightly: a baseline with no
        # memory state behind it can never be scored as a measurement of that
        # state. Refuse clearly rather than letting the database refuse opaquely.
        head = self._brain.head()
        if not head:
            raise BrainUnavailable(
                f"cannot record a baseline: no brain commit readable at "
                f"{self._brain.path}. A score with no memory state behind it "
                "measures nothing."
            )

        eval_run_id = new_ulid(now_ms())
        self._repo.connection.execute(
            "INSERT INTO eval_runs (id, week_of, started_at_ms, brain_sha, code_sha, "
            "judge_model, judge_provider, rubric_sha, is_synthetic) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (eval_run_id, week_of, now_ms(), head, code_sha,
             AWAITING, AWAITING, rubric.sha, int(self._is_synthetic)),
        )
        return eval_run_id

    def pinned_rubric_sha(self, eval_run_id: str) -> str:
        row = self._repo.connection.execute(
            "SELECT rubric_sha FROM eval_runs WHERE id = ?", (eval_run_id,)
        ).fetchone()
        if row is None:
            raise ValueError(f"unknown eval run {eval_run_id!r}")
        return row["rubric_sha"]

    def recorded_runs(self) -> list[RecordedRun]:
        """Every run and what it pinned, oldest first.

        A pinned hash nobody can read is pinned in name only. This exists so
        reconciling one is a supported command rather than SQL written from
        memory against a database on another machine.
        """
        return [
            RecordedRun(
                eval_run_id=r["id"],
                week_of=r["week_of"],
                rubric_sha=r["rubric_sha"],
                brain_sha=r["brain_sha"],
                judge_model=r["judge_model"],
            )
            for r in self._repo.connection.execute(
                # The curve is the real instance's. A demo deployment's scores
                # are a number like any other once they are in the table, and
                # there is no way to tell them apart afterwards — which is why
                # the exclusion is here and not left to whoever reads it.
                "SELECT id, week_of, rubric_sha, brain_sha, judge_model FROM eval_runs "
                "WHERE is_synthetic = 0 ORDER BY started_at_ms"
            )
        ]

    def awaiting_scoring(self) -> list[str]:
        return [
            r["id"]
            for r in self._repo.connection.execute(
                "SELECT id FROM eval_runs WHERE judge_model = ? AND is_synthetic = 0 "
                "ORDER BY started_at_ms",
                (AWAITING,),
            )
        ]

    def brain_at_baseline(self, eval_run_id: str):
        """The brain as it was when the baseline was recorded.

        Not the working tree. Generating from current memory and labeling the
        result with an old commit would make the pinning decorative — the number
        would carry a state that never shaped it.
        """
        row = self._repo.connection.execute(
            "SELECT brain_sha FROM eval_runs WHERE id = ?", (eval_run_id,)
        ).fetchone()
        if row is None:
            raise ValueError(f"unknown eval run {eval_run_id!r}")
        if not row["brain_sha"]:
            raise BrainUnavailable(
                f"eval run {eval_run_id!r} recorded no brain commit; its outputs "
                "cannot be attributed to a memory state"
            )
        return self._brain.topic_files_at(row["brain_sha"])

    def score(
        self,
        eval_run_id: str,
        *,
        judge: Judge | None,
        generate,
        rubric: Rubric,
    ) -> RunSummary:
        """Generate an output per sample and grade it.

        `generate` takes the prompt and the brain as it was, and returns text.
        Kept as a parameter rather than a dependency so the runner is exercisable
        without a model, and so the caller decides which provider produces the
        output.
        """
        if judge is None:
            raise NoJudgeConfigured(
                "no judge configured; refusing to record unscored results as scored"
            )

        # The rubric arrives from disk and the run recorded a hash. Nothing
        # compared them until now, so a rubric edited after a baseline was
        # recorded would have graded that baseline and stamped the result with a
        # hash that did not produce it — a wrong number wearing the pinning that
        # exists to make numbers trustworthy.
        pinned = self.pinned_rubric_sha(eval_run_id)
        if rubric.sha != pinned:
            raise RubricMismatch(
                f"eval run {eval_run_id} pinned rubric {pinned[:12]}, but "
                f"{rubric.path} hashes to {rubric.sha[:12]}. Scoring would grade "
                "this run against a rubric it never used. Restore the rubric it "
                "pinned, or record a new baseline under the rubric on disk — a "
                "rubric is superseded, never edited in place."
            )

        brain = self.brain_at_baseline(eval_run_id)
        complete = True

        for prompt_id, slug, prompt in self.active_prompts():
            for index in range(self._samples):
                try:
                    output = generate(prompt=prompt, brain=brain, sample=index)
                    judgement = judge.score(output=output, rubric=rubric.text, prompt=prompt)
                except (UnreadableJudgement, BadOutput, RuntimeError) as exc:
                    # A failed sample is recorded as a failure and omitted from
                    # the scores. A zero would be indistinguishable from a
                    # genuinely poor answer.
                    complete = False
                    self._repo.insert_failure(
                        failure_type="bad_output",
                        signature=f"eval:{slug}:{type(exc).__name__}",
                        message=str(exc) or type(exc).__name__,
                    )
                    continue
                self._record_result(eval_run_id, prompt_id, index, judgement)

        self._repo.connection.execute(
            "UPDATE eval_runs SET judge_model = ?, judge_model_version = ?, "
            "judge_provider = ?, ended_at_ms = ? WHERE id = ?",
            (judge.name, judge.version, "configured", now_ms() if complete else None,
             eval_run_id),
        )
        return self.summarize(eval_run_id)

    def _record_result(
        self, eval_run_id: str, prompt_id: str, sample: int, judgement: Judgement
    ) -> None:
        import json

        self._repo.connection.execute(
            "INSERT INTO eval_results (id, eval_run_id, eval_prompt_id, sample_index, "
            "score, subscores_json, is_synthetic) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (new_ulid(now_ms()), eval_run_id, prompt_id, sample,
             float(judgement.total), json.dumps(judgement.scores),
             int(self._is_synthetic)),
        )

    # -- reading -----------------------------------------------------------

    def curve(self, earlier_id: str, later_id: str) -> Curve:
        """Compare two runs, or refuse to.

        Every refusal below is a way the reported number would measure something
        other than what it appears to. They raise rather than warn: this output
        ends up in a submission, and a warning on a report nobody re-reads is
        not a guard.
        """
        earlier = self.summarize(earlier_id)
        later = self.summarize(later_id)

        synthetic = [
            run_id
            for run_id in (earlier_id, later_id)
            if self._repo.connection.execute(
                "SELECT is_synthetic FROM eval_runs WHERE id = ?", (run_id,)
            ).fetchone()["is_synthetic"]
        ]
        if synthetic:
            raise NotComparable(
                f"{', '.join(synthetic)} is synthetic. A generated run's scores are "
                "numbers like any other once they are in the table, which is why they "
                "are excluded here rather than left to whoever reads the output."
            )

        for summary in (earlier, later):
            if not summary.prompts:
                raise NotComparable(
                    f"{summary.eval_run_id} has no results; it has been recorded "
                    "but never scored"
                )
            if not summary.complete:
                raise NotComparable(
                    f"{summary.eval_run_id} is incomplete. A partial run is not "
                    "comparable to a whole one: averaging over the samples that "
                    "survived hides which prompts did not."
                )

        if earlier.rubric_sha != later.rubric_sha:
            raise NotComparable(
                f"different rubrics — {earlier.rubric_sha[:12]} and "
                f"{later.rubric_sha[:12]}. A rubric hash is pinned to a measurement "
                "so that two runs graded against different text cannot be compared "
                "without anyone noticing."
            )
        if earlier.judge_model != later.judge_model:
            raise NotComparable(
                f"different judges — {earlier.judge_model} and {later.judge_model}. "
                "Two judges are two instruments, and a curve across instruments is "
                "not a curve."
            )
        if earlier.brain_sha and earlier.brain_sha == later.brain_sha:
            raise NotComparable(
                f"both runs pin brain {earlier.brain_sha[:12]}. The brain did not "
                "change between them, so the difference is sampling noise and "
                "reporting it as a result would be reporting the noise."
            )

        return Curve(
            earlier=earlier, later=later, dimensions=self._dimensions(earlier_id, later_id)
        )

    def _dimensions(self, earlier_id: str, later_id: str) -> list[DimensionDelta]:
        """Per dimension, read from `subscores_json` — which nothing read back
        until this.

        A dimension absent from a run's subscores is left out rather than
        reported as zero. Zero is a real score meaning the worst possible
        answer, and the same argument that makes an unparseable judgement a
        typed failure makes a missing dimension one here.
        """
        earlier = self._subscores(earlier_id)
        later = self._subscores(later_id)
        return [
            DimensionDelta(
                dimension=name,
                earlier=statistics.fmean(earlier[name]),
                later=statistics.fmean(later[name]),
            )
            for name in DIMENSIONS
            if earlier.get(name) and later.get(name)
        ]

    def _subscores(self, eval_run_id: str) -> dict[str, list[float]]:
        out: dict[str, list[float]] = {}
        for row in self._repo.connection.execute(
            "SELECT subscores_json FROM eval_results WHERE eval_run_id = ?",
            (eval_run_id,),
        ):
            if not row["subscores_json"]:
                continue
            try:
                parsed = json.loads(row["subscores_json"])
            except json.JSONDecodeError:
                # Unreadable detail is skipped rather than counted as zero, for
                # the same reason an unreadable judgement is a typed failure.
                continue
            for name, value in parsed.items():
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    out.setdefault(name, []).append(float(value))
        return out

    def summarize(self, eval_run_id: str) -> RunSummary:
        run = self._repo.connection.execute(
            "SELECT * FROM eval_runs WHERE id = ?", (eval_run_id,)
        ).fetchone()
        if run is None:
            raise ValueError(f"unknown eval run {eval_run_id!r}")

        by_slug: dict[str, list[int]] = {}
        for row in self._repo.connection.execute(
            "SELECT p.slug AS slug, r.score AS score FROM eval_results r "
            "JOIN eval_prompts p ON p.id = r.eval_prompt_id "
            "WHERE r.eval_run_id = ? ORDER BY p.slug, r.sample_index",
            (eval_run_id,),
        ):
            by_slug.setdefault(row["slug"], []).append(int(row["score"]))

        expected = len(self.active_prompts()) * self._samples
        recorded = sum(len(v) for v in by_slug.values())
        return RunSummary(
            eval_run_id=eval_run_id,
            brain_sha=run["brain_sha"],
            rubric_sha=run["rubric_sha"],
            judge_model=run["judge_model"],
            complete=run["judge_model"] != AWAITING and recorded == expected,
            prompts=[PromptSummary(slug=s, samples=v) for s, v in sorted(by_slug.items())],
        )
