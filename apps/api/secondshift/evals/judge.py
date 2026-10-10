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

from ..providers.base import STOPPED_CLEANLY, Message, Reasoner

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


def last_object(text: str) -> str:
    """The last top-level JSON object in a completion, or "".

    A forward scan tracking three things — whether it is inside a string,
    whether the last character was an escape, and how deep the braces go. Not a
    regex: a regex for nested JSON is either wrong or unreadable, and this is
    read by whoever is debugging a refused run.

    Forward rather than backwards, which the first draft tried. Going backwards
    a quote is ambiguous — the same character opens and closes a string, and
    which one it is depends on parse state that only exists ahead of it.
    Forwards, a quote outside a string always opens one.

    The last object rather than the first, because a model that restates its
    answer puts the final form last. Braces inside strings are skipped, so a
    note containing `}` cannot truncate the object around it — and the note is
    the one field a model writes freely.
    """
    depth = 0
    started = None
    found = ""
    in_string = False
    escaped = False
    for index, char in enumerate(text):
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            if depth == 0:
                started = index
            depth += 1
        elif char == "}":
            if depth > 0:
                depth -= 1
                if depth == 0 and started is not None:
                    found = text[started:index + 1]
    return found


class ModelJudge:
    """Scores an output by asking a model for them.

    Bound to the `Reasoner` interface rather than to a provider, so which model
    grades is a call site and not a code change — and so no model identifier
    lands outside the providers package. `name` is read from the provider at
    runtime, which is also what makes it the model that actually graded the run
    rather than what someone wrote down.

    Writes no telemetry. `Reasoner.complete` records the call, the failure and a
    completion that did not stop cleanly; a judge recording its own would be a
    second writer.
    """

    def __init__(self, reasoner: Reasoner, *, policy: str, version: str) -> None:
        """`policy` and `version` have no defaults, deliberately.

        A default policy is a remote call nobody chose, and the airlock asserts
        policy on every completion precisely so the choice is visible. A default
        version is a pin that floats: `eval_runs.judge_model_version` exists so
        that restarting a server against another checkpoint cannot change what a
        past run claims about itself.
        """
        self._reasoner = reasoner
        self._policy = policy
        self.version = version

    @property
    def name(self) -> str:
        return self._reasoner.model

    def score(self, *, output: str, rubric: str, prompt: str) -> Judgement:
        completion = self._reasoner.complete(
            [Message("user", _ASK.format(rubric=rubric, prompt=prompt, output=output))],
            policy=self._policy,
        )
        if completion.finish_reason != STOPPED_CLEANLY:
            # Before parsing, not after. JSON truncated at a token limit can
            # parse as a smaller valid object, so a judgement missing two
            # dimensions would score on the rest — a wrong number that reads
            # like a right one. The first real night lost three stages to
            # exactly this shape of partial output being read as whole.
            raise UnreadableJudgement(
                f"the judge stopped: {completion.finish_reason}. A truncated "
                "judgement can still parse, so it is refused rather than read."
            )
        found = last_object(completion.text)
        if not found:
            raise UnreadableJudgement(
                "the judge wrote no JSON object. Scores read out of prose would "
                "make the measurement depend on the model's formatting, which is "
                "what pinning the judge exists to exclude."
            )
        return Judgement.parse(found)


#: Asks for the object and nothing about its surroundings. The judge tolerates
#: deliberation before the object because the served checkpoint emits it
#: inconsistently — sometimes delimited, sometimes as bare prose — so demanding
#: a bare object would refuse every real completion.
_ASK = """\
Score the answer below against this rubric.

RUBRIC
{rubric}

QUESTION
{prompt}

ANSWER
{output}

Reply with one JSON object and nothing that needs to be read as part of it:
{{"scores": {{"interrogation": <1-5>, "fit": <1-5>, "judgement": <1-5>,
"actionability": <1-5>, "voice": <1-5>}}, "note": "<one sentence>"}}

Every dimension is required and every value is a whole number from 1 to 5.
"""
