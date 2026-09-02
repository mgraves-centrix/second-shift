"""Agents: six fixed roles, versioned prompts, and recorded invocations.

The roster pins each prompt by content hash so that an eight-week curve
measures the brain rather than a prompt that changed underneath it.
"""

from .invoke import AgentTurn, invoke, strip_reasoning
from .roster import (
    PromptEditedInPlace,
    PromptFileMissing,
    discover,
    permitted_roles,
    register,
)

__all__ = [
    "AgentTurn",
    "PromptEditedInPlace",
    "PromptFileMissing",
    "discover",
    "invoke",
    "permitted_roles",
    "register",
    "strip_reasoning",
]
