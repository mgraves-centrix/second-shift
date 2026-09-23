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
#:
#: A heading may end with `{#slug}` to name the prompt explicitly. It should:
#: derived slugs come from the whole heading, and these headings explain why a
#: prompt was chosen rather than what it asks — so a derived slug labels eight
#: weeks of charts with an argument instead of a name.
_CANDIDATE = re.compile(
    r"^###\s+(\d+)\.\s+(.+?)\s*$\n(.*?)(?=^###\s+\d+\.|\Z)", re.M | re.S
)
_EXPLICIT_SLUG = re.compile(r"\s*\{#([a-z0-9-]+)\}\s*$")
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
        explicit = _EXPLICIT_SLUG.search(label)
        clean = _EXPLICIT_SLUG.sub("", label).strip()
        found.append(
            PromptCandidate(
                slug=explicit.group(1) if explicit else _slugify(clean),
                label=clean,
                prompt=quoted,
            )
        )
    return found


def load_rubric(path: str | Path) -> Rubric:
    resolved = Path(path)
    return Rubric(path=resolved, text=resolved.read_text())


@dataclass(frozen=True, slots=True)
class Threshold:
    """What would falsify the claim, fixed before the result existed.

    Hashed like the rubric, and for the same reason: a bar edited after the
    number is a bar that was never a bar. `curve` prints this hash beside its
    verdict, so the edit is visible where the result is read.

    The numbers are held here rather than in the file because code that parsed
    its own policy out of prose would be a second place for the policy to live.
    The file is the argument; these two are what the argument concluded, and
    `test_the_rule_matches_the_file` holds them together.
    """

    path: Path
    text: str

    #: Twice the standard error of the mean per-prompt change. One is about 68%
    #: and would call noise a result; three is a bar six prompts cannot clear
    #: even if the brain genuinely helps, which makes the claim unfalsifiable
    #: the other way. Two is the conventional rule of thumb, and it is a rule of
    #: thumb: no p-value is computed and none should be quoted.
    standard_errors: float = 2.0

    #: And at least this share of the prompts moving the same way, because the
    #: claim is about the brain rather than about one kind of question.
    agreeing_share: float = 2 / 3

    @property
    def sha(self) -> str:
        """Content hash. Follows the file, not the commit that touched it."""
        return hashlib.sha256(self.text.encode()).hexdigest()

    @property
    def fixed_on(self) -> str:
        """The date in the file's own first line, not a mtime.

        A modification time is a property of a checkout. This has to survive
        being cloned by somebody checking whether the bar predated the number.
        """
        found = re.search(r"\*\*Fixed (\d{4}-\d{2}-\d{2})", self.text)
        if found is None:
            raise ValueError(
                f"{self.path} does not say when it was fixed, which is the one "
                "thing a falsification threshold has to say"
            )
        return found.group(1)


def load_threshold(path: str | Path) -> Threshold:
    resolved = Path(path)
    return Threshold(path=resolved, text=resolved.read_text())
