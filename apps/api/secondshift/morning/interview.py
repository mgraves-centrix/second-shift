"""Raising the questions, and recording the answers.

The interviewer reads assembled facts and produces questions. It is **not**
handed the raw entry text: its job is "what got stuck", which is a property of
the run, and not passing the idea means a `cloud-assisted` interview does not put
the original in front of a remote model a second time.

An answer is always submitted **against a specific decision id**. There is no
path here that accepts free-form text and routes it somewhere, and that absence
is the scope boundary made structural rather than remembered —
`NOT_BUILDING.md` excludes a general chat interface by name, and it is the way
this capability is most likely to go wrong.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from ..agents.invoke import invoke
from ..db.repository import Repository
from ..providers.base import Reasoner
from ..telemetry.recorder import Recorder
from .briefing import Briefing, NightLine

#: How the interviewer is asked to shape a question so both halves survive.
#: A question without its rationale is a quiz — the prompt's phrase — so the
#: parser refuses one rather than storing half a question.
_QUESTION = re.compile(
    r"^\s*Q:\s*(?P<question>.+?)\s*$\n^\s*Why:\s*(?P<rationale>.+?)\s*$",
    re.M,
)

#: Appended to the interviewer's own prompt file. The prompt is the subject's to
#: write; this is the machine-readable shape the parser needs, and it is kept
#: here rather than in the prompt so that changing the format does not change
#: `prompt_sha` and reset the role's eight-week curve.
FORMAT_INSTRUCTION = """
Write each question as exactly two lines:

Q: <the question>
Why: <what you tried, why it stopped, and what you need from them>

Nothing else. A question without its `Why:` is discarded rather than asked.
"""


@dataclass(frozen=True, slots=True)
class RaisedQuestion:
    decision_id: str
    question: str
    rationale: str


def facts_for(nights: tuple[NightLine, ...]) -> str:
    """The night as the interviewer sees it: stages and outcomes, not the idea."""
    lines: list[str] = []
    for night in nights:
        lines.append(f"Run {night.run_id} ({night.night_of}), outcome {night.outcome}:")
        for stage in night.stages:
            detail = f" — {stage.reason}" if stage.reason else ""
            produced = f", produced {len(stage.artifacts)}" if stage.artifacts else ""
            lines.append(f"  {stage.stage}: {stage.status}{produced}{detail}")
    return "\n".join(lines)


#: The shape of an unfilled placeholder in `FORMAT_INSTRUCTION`. A model that
#: echoes the template back — which the `cloud` profile's `EchoReasoner` does by
#: construction — would otherwise have `<the question>` stored as something to
#: ask a person over coffee. Found by running the real command end to end and
#: reading what landed, not by a test.
_PLACEHOLDER = re.compile(r"<[^>]+>")


def parse_questions(text: str) -> list[tuple[str, str]]:
    """Question and rationale pairs, in order. Half a question is not a question.

    A model that emitted a bare `Q:` with no `Why:` produced something this
    refuses to store: the rationale is what separates a question from a quiz,
    and storing the question alone would lose the distinction permanently.

    A pair that still carries a template placeholder is discarded for the same
    reason the quality bar forbids lorem text — a question nobody wrote is worse
    than no question, because the morning presents it as if somebody had.
    """
    pairs = [
        (m.group("question").strip(), m.group("rationale").strip())
        for m in _QUESTION.finditer(text)
    ]
    return [
        (q, why)
        for q, why in pairs
        if q and why and not _PLACEHOLDER.search(q) and not _PLACEHOLDER.search(why)
    ]


def raise_questions(
    repo: Repository,
    recorder: Recorder,
    reasoner: Reasoner,
    briefing: Briefing,
    *,
    agent_id: str,
    prompt_path,
    entry_id: str,
    policy: str,
    run_id: str | None = None,
) -> list[RaisedQuestion]:
    """Run the interviewer over the night and store what it asks.

    Every decision names the invocation that raised it, so a prompt change is
    visible in the record rather than inferred from a date.
    """
    turn = invoke(
        recorder,
        reasoner,
        role="interviewer",
        agent_id=agent_id,
        prompt_path=prompt_path,
        task=FORMAT_INSTRUCTION,
        policy=policy,
        run_id=run_id,
        stage="interview",
        context=facts_for(briefing.nights),
    )

    raised: list[RaisedQuestion] = []
    for question, rationale in parse_questions(turn.text):
        decision_id = repo.insert_decision(
            entry_id=entry_id,
            question=question,
            rationale=rationale,
            status="open",
            raised_by_run_id=run_id,
            raised_by_invocation_id=turn.invocation_id,
        )
        raised.append(RaisedQuestion(decision_id, question, rationale))
    return raised


def answer(
    repo: Repository,
    decision_id: str,
    *,
    text: str,
    status: str,
    modality: str = "text",
) -> None:
    """Record an answer against one question.

    Takes a decision id, never an instruction. `answer_decision` already refuses
    an unknown or already-answered decision, so a submission against something
    the system never asked cannot be recorded.
    """
    repo.answer_decision(
        decision_id, answer=text, status=status, answer_modality=modality
    )


def queued_for_tonight(repo: Repository) -> list:
    """Answers waiting to be taken by a run, oldest first."""
    return repo.connection.execute(
        "SELECT * FROM decisions WHERE status = 'queued-for-tonight' "
        "AND consumed_by_run_id IS NULL ORDER BY answered_at_ms, id"
    ).fetchall()


def mark_consumed(repo: Repository, decision_id: str, run_id: str) -> None:
    """Record which run took this answer as input.

    The visible half of "answering changes tonight": without it a
    `queued-for-tonight` decision would sit forever looking pending even after
    the run that used it finished.
    """
    cursor = repo.connection.execute(
        "UPDATE decisions SET consumed_by_run_id = ? "
        "WHERE id = ? AND consumed_by_run_id IS NULL",
        (run_id, decision_id),
    )
    if cursor.rowcount != 1:
        raise ValueError(f"decision {decision_id!r} is unknown or already consumed")
