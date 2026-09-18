"""What the night proposes to change about what the system believes.

ADR 0007 makes the brain's `git diff` the evidence that this system learns, and
a diff is only worth reading if each change is a sentence somebody could argue
with. So the distiller does not rewrite a topic file: it proposes beliefs, each
one sentence, each naming the line it supersedes or saying it supersedes
nothing.

The asymmetry that shapes every rule here: an appended belief that is wrong is
visible and revertible, and a silently deleted one is neither. So nothing is
removed unless the distiller named exactly one existing line, and everything
else is appended.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .repo import BrainRepo, PROFILE, STYLE_GUIDE

#: The two files a night may revise. Skills are written by hand for now: they
#: are instructions the system follows, and a wrong one changes behavior rather
#: than context.
REVISABLE = (PROFILE, STYLE_GUIDE)

#: Beliefs one night may propose. A night that wants to change six things about
#: a person after six hours of work on one idea has not learned six things.
#: Refused whole rather than truncated: taking the first three of seven would
#: apply an arbitrary subset of an argument the model made as a set.
MAX_BELIEFS = 3

_BLOCK = re.compile(
    r"^\s*BELIEF:\s*(?P<belief>.+?)\s*$\n^\s*REPLACES:\s*(?P<replaces>.+?)\s*$",
    re.M,
)
_PLACEHOLDER = re.compile(r"<[^>]+>")
_WORDS = re.compile(r"[A-Za-z]{2,}")
_NOTHING = frozenset({"none", "nothing", "n/a", "-"})


@dataclass(frozen=True, slots=True)
class Belief:
    """One sentence, and the line it supersedes if it supersedes one."""

    statement: str
    replaces: str | None


def parse_beliefs(text: str) -> list[Belief]:
    """The beliefs a completion proposed. Half a block is not a proposal.

    A `BELIEF:` with no `REPLACES:` under it is discarded for the reason the
    interviewer discards a question with no rationale: the missing half is the
    one that says whether this revises something or adds to it, and guessing
    would either lose a belief or overwrite one.
    """
    beliefs: list[Belief] = []
    for match in _BLOCK.finditer(text):
        statement = match.group("belief").strip()
        replaces = match.group("replaces").strip()
        if not _WORDS.search(statement) or _PLACEHOLDER.search(statement):
            continue
        supersedes = None if replaces.lower() in _NOTHING else replaces
        if supersedes is not None and (
            not _WORDS.search(supersedes) or _PLACEHOLDER.search(supersedes)
        ):
            supersedes = None
        beliefs.append(Belief(statement, supersedes))
    if len(beliefs) > MAX_BELIEFS:
        return []
    return beliefs


def apply_beliefs(brain: BrainRepo, beliefs: list[Belief]) -> list[str]:
    """Write the proposed beliefs into the brain. Returns the files changed.

    A belief that names exactly one existing line replaces it. Anything else is
    appended: a line that is not there, or that is there twice, is a belief the
    distiller did not successfully point at, and appending keeps what it said
    while deleting nothing.

    Where the named line lives decides which file the belief lands in, so a
    revision to the style guide stays in the style guide. A belief that names
    nothing goes to the profile.
    """
    if not beliefs:
        return []

    contents = {
        name: (brain.path / name).read_text() if (brain.path / name).is_file() else ""
        for name in REVISABLE
    }
    changed: set[str] = set()

    for belief in beliefs:
        target = PROFILE
        if belief.replaces is not None:
            for name in REVISABLE:
                if contents[name].count(belief.replaces) >= 1:
                    target = name
                    break
        lines = contents[target].splitlines()
        matches = [i for i, line in enumerate(lines) if line.strip() == (belief.replaces or "").strip()]
        if belief.replaces is not None and len(matches) == 1:
            lines[matches[0]] = belief.statement
            contents[target] = "\n".join(lines) + "\n"
        else:
            body = contents[target].rstrip("\n")
            contents[target] = f"{body}\n\n{belief.statement}\n" if body else f"{belief.statement}\n"
        changed.add(target)

    for name in sorted(changed):
        (brain.path / name).write_text(contents[name])
    return sorted(changed)
