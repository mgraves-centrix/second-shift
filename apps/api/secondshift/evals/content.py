"""Prompts and the rubric, loaded from files.

Content rather than code: editing a prompt is not a code change, and the
rubric's hash is what makes two scores comparable. A rubric embedded in a module
would be versioned by commit rather than by content, so an unrelated change to
the file would appear to invalidate every prior score.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

#: Candidate prompts are written as `### <n>. <label>` followed by a blockquote
#: holding the prompt itself. The blockquote is the prompt; the prose around it
#: is the argument for including it, which is for a human and not for the runner.
_CANDIDATE = re.compile(
    r"^###\s+(\d+)\.\s+(.+?)\s*$\n(.*?)(?=^###\s+\d+\.|\Z)", re.M | re.S
)
_QUOTE_LINE = re.compile(r"^>\s?(.*)$", re.M)


@dataclass(frozen=True, slots=True)
class PromptCandidate:
    slug: str
    label: str
    prompt: str


@dataclass(frozen=True, slots=True)
class Rubric:
    path: Path
    text: str

    @property
    def sha(self) -> str:
        """Content hash. Follows the file, not the commit that touched it."""
        return hashlib.sha256(self.text.encode()).hexdigest()


def _slugify(label: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")
    return cleaned[:60] or "prompt"


def load_prompts(path: str | Path) -> list[PromptCandidate]:
    """Parse candidate prompts from their markdown.

    A candidate with no blockquote is prose about the set rather than a prompt,
    and is skipped — the file is written to be read by a person first.
    """
    text = Path(path).read_text()
    found: list[PromptCandidate] = []
    for _number, label, body in _CANDIDATE.findall(text):
        quoted = "\n".join(_QUOTE_LINE.findall(body)).strip()
        if not quoted:
            continue
        found.append(
            PromptCandidate(slug=_slugify(label), label=label.strip(), prompt=quoted)
        )
    return found


def load_rubric(path: str | Path) -> Rubric:
    resolved = Path(path)
    return Rubric(path=resolved, text=resolved.read_text())
