"""The morning: what the night did, what it could not decide, and your answers.

`briefing` assembles facts from rows with no model call, so principle 3 holds
structurally — the morning shows what the night produced even when the
interviewer cannot run. `interview` turns those facts into questions and records
answers against them.
"""

from .briefing import Briefing, NightLine, Question, StageLine, assemble, boundary_ms
from .interview import (
    RaisedQuestion,
    answer,
    facts_for,
    mark_consumed,
    parse_questions,
    queued_for_tonight,
    raise_questions,
)

__all__ = [
    "Briefing",
    "NightLine",
    "Question",
    "RaisedQuestion",
    "StageLine",
    "answer",
    "assemble",
    "boundary_ms",
    "facts_for",
    "mark_consumed",
    "parse_questions",
    "queued_for_tonight",
    "raise_questions",
]
