"""The measurement spine.

A fixed prompt set, run repeatedly, scored against a fixed rubric by a pinned
judge, and attributed to the exact brain state that produced each output.

Everything here exists to make one comparison trustworthy: the same prompts in
week 1 and week 8. The scoring is the obvious part; the pinning is the part that
makes a number mean anything.
"""

from .content import Rubric, load_prompts, load_rubric
from .judge import Judgement, Judge, StubJudge, UnreadableJudgement
from .runner import EvalRunner, RunSummary

__all__ = [
    "EvalRunner",
    "Judge",
    "Judgement",
    "Rubric",
    "RunSummary",
    "StubJudge",
    "UnreadableJudgement",
    "load_prompts",
    "load_rubric",
]
