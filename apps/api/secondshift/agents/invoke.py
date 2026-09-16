"""Running one agent: a role, a prompt, a policy, and a recorded call.

Nothing here writes telemetry. `Recorder.invocation` opens and closes the
invocation row with parentage from the surrounding context, and `Reasoner`
records the model call — this module's whole job is to assemble the messages
and hand them over.

The policy is passed in and passed through. It is never defaulted and never
read from ambient state: an agent that infers its own policy is an agent that
can infer the wrong one, and principle 2 is not a thing to be inferred.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..providers.base import STOPPED_CLEANLY, Message, Reasoner
from ..telemetry.failures import BadOutput
from ..telemetry.recorder import Recorder


class TurnDidNotFinish(BadOutput):
    """The model stopped for a reason other than finishing, usually the token limit.

    A reasoning model that runs out of budget stops inside its deliberation,
    before it closes it, so what comes back is half a thought with no answer in
    it. Accepting that as a turn is how the first real night recorded a brief
    that was the model's unfinished notes, and how each later stage — handed
    that as context — copied it forward instead of doing its own work.
    """

#: What the served checkpoint wraps its deliberation in. Stripped here rather
#: than in the provider: `VllmReasoner` returns completions whole on purpose,
#: because a splitter that guesses wrong deletes the answer and corrupts token
#: accounting. By this layer the tokens are already counted, so trimming
#: changes only what a reader sees.
THINK_CLOSE = "</think>"


@dataclass(frozen=True, slots=True)
class AgentTurn:
    """What one agent produced, and what it was pinned to."""

    role: str
    agent_id: str
    text: str
    raw_text: str
    #: The `agent_invocations` row this turn opened. Carried out because an
    #: artifact records the invocation that produced it, and without this the
    #: caller has only the agent id — which is a different table, and the
    #: foreign key catches the confusion rather than storing it.
    invocation_id: str | None = None

    @property
    def showed_its_reasoning(self) -> bool:
        """True when the model emitted deliberation the reader did not need.

        Worth surfacing rather than silently trimming: a brief that needed
        trimming is evidence about the prompt, and the prompt is the thing
        under measurement.
        """
        return self.text != self.raw_text


def strip_reasoning(text: str) -> str:
    """Drop everything up to and including the model's own close delimiter.

    Conditional on the delimiter being present. A model that stops emitting it
    degrades to verbose output, which somebody notices, rather than to an empty
    brief, which nobody does until it matters.
    """
    marker = text.rfind(THINK_CLOSE)
    if marker == -1:
        return text
    return text[marker + len(THINK_CLOSE) :].strip()


def invoke(
    recorder: Recorder,
    reasoner: Reasoner,
    *,
    role: str,
    agent_id: str,
    prompt_path: Path,
    task: str,
    policy: str,
    run_id: str | None = None,
    stage: str | None = None,
    context: str = "",
) -> AgentTurn:
    """One agent turn, recorded.

    `context` is whatever the caller assembled — this takes what it is handed
    and does no retrieval of its own.
    """
    system = prompt_path.read_text()
    messages = [Message("system", system)]
    if context.strip():
        messages.append(Message("user", f"Context you may use:\n\n{context}"))
    messages.append(Message("user", task))

    with recorder.invocation(agent_id, run_id=run_id, stage=stage) as invocation_id:
        completion = reasoner.complete(messages, policy=policy, effort=None)
        # Inside the invocation, so it closes as a failure and the failure is
        # recorded against it. The call itself is already recorded: refusing the
        # text does not unspend the tokens.
        if completion.finish_reason != STOPPED_CLEANLY:
            raise TurnDidNotFinish(
                f"{role} stopped before finishing ({completion.finish_reason}) after "
                f"{completion.completion_tokens} completion tokens"
            )

    return AgentTurn(
        role=role,
        agent_id=agent_id,
        text=strip_reasoning(completion.text),
        raw_text=completion.text,
        invocation_id=invocation_id,
    )
