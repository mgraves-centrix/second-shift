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

import statistics
from dataclasses import dataclass, field

from ..brain.repo import BrainRepo, BrainUnavailable
from ..db.connection import now_ms
from ..db.ids import new_ulid
from ..db.repository import Repository
from ..telemetry.failures import BadOutput
from .content import PromptCandidate, Rubric
from .judge import Judge, Judgement, UnreadableJudgement

#: A run with no judge recorded has inputs but no scores. Stored in the judge
#: column rather than a status column: the absence *is* the state, and a
#: separate flag could disagree with it.
AWAITING = "awaiting-scoring"


class NoJudgeConfigured(RuntimeError):
    """Scoring was attempted with nothing to score with."""


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
    ) -> None:
        self._repo = repo
        self._brain = brain if brain is not None else BrainRepo()
        self._samples = samples

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
                "created_at_ms, active) VALUES (?, ?, ?, ?, ?, ?, 0)",
                (new_ulid(now_ms()), candidate.slug, candidate.prompt,
                 str(rubric.path), rubric.sha, now_ms()),
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
            "judge_model, judge_provider, rubric_sha) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (eval_run_id, week_of, now_ms(), head, code_sha,
             AWAITING, AWAITING, rubric.sha),
        )
        return eval_run_id

    def awaiting_scoring(self) -> list[str]:
        return [
            r["id"]
            for r in self._repo.connection.execute(
                "SELECT id FROM eval_runs WHERE judge_model = ? ORDER BY started_at_ms",
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
            "score, subscores_json) VALUES (?, ?, ?, ?, ?, ?)",
            (new_ulid(now_ms()), eval_run_id, prompt_id, sample,
             float(judgement.total), json.dumps(judgement.scores)),
        )

    # -- reading -----------------------------------------------------------

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
