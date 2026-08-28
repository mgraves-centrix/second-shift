"""Scoring.

The judge returns a value per rubric dimension as structured data. Extracting
numbers from prose would make the measurement depend on the judge's formatting,
which is exactly the drift that pinning the judge exists to exclude — a model
that starts writing "4/5" instead of "Score: 4" would show as a change in the
brain.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Protocol

#: The rubric's five dimensions. Fixed alongside the rubric itself: adding one
#: changes what a total means, so it changes the rubric hash too.
DIMENSIONS = ("interrogation", "fit", "judgement", "actionability", "voice")
MIN_SCORE, MAX_SCORE = 1, 5


class UnreadableJudgement(ValueError):
    """A judgement that is not a valid set of scores.

    Recorded as a failure rather than a zero. A zero is a real score meaning "the
    worst possible answer", and a judge that malfunctioned is not evidence that
    the system performed badly.
    """


@dataclass(frozen=True, slots=True)
class Judgement:
    scores: dict[str, int]
    note: str = ""

    @property
    def total(self) -> int:
        return sum(self.scores.values())

    @classmethod
    def parse(cls, payload: str | dict) -> Judgement:
        """Read structured scores, refusing anything that is not one."""
        try:
            data = json.loads(payload) if isinstance(payload, str) else payload
        except (json.JSONDecodeError, TypeError) as exc:
            raise UnreadableJudgement(f"judgement is not structured data: {exc}") from exc
        if not isinstance(data, dict):
            raise UnreadableJudgement(f"judgement is {type(data).__name__}, not an object")

        raw_scores = data.get("scores", data)
        if not isinstance(raw_scores, dict):
            raise UnreadableJudgement("judgement carries no scores object")

        scores: dict[str, int] = {}
        for dimension in DIMENSIONS:
            if dimension not in raw_scores:
                raise UnreadableJudgement(f"judgement is missing dimension {dimension!r}")
            value = raw_scores[dimension]
            if not isinstance(value, int) or isinstance(value, bool):
                raise UnreadableJudgement(
                    f"dimension {dimension!r} is {value!r}, not a whole number"
                )
            if not MIN_SCORE <= value <= MAX_SCORE:
                raise UnreadableJudgement(
                    f"dimension {dimension!r} is {value}, outside {MIN_SCORE}-{MAX_SCORE}"
                )
            scores[dimension] = value
        return cls(scores=scores, note=str(data.get("note", "")))


class Judge(Protocol):
    """Scores one output against the rubric."""

    name: str
    version: str

    def score(self, *, output: str, rubric: str, prompt: str) -> Judgement: ...


@dataclass(slots=True)
class StubJudge:
    """A deterministic judge, for exercising the runner without a model.

    Not a mock of the thing under test: the runner is what is under test, and the
    judge is its collaborator. Scores vary with the output so a test can tell one
    result from another.
    """

    name: str = "stub-judge"
    version: str = "1"
    base: int = 3

    def score(self, *, output: str, rubric: str, prompt: str) -> Judgement:
        spread = len(output) % 3
        return Judgement(
            scores={d: min(MAX_SCORE, max(MIN_SCORE, self.base + (i + spread) % 2))
                    for i, d in enumerate(DIMENSIONS)},
            note="stub",
        )
