"""Deriving a title from an entry's own content.

Deterministic and model-free by requirement. A model-derived title would need an
agent row, an invocation, a policy-carrying model call and a priced model — so
every capture would fail until cloud pricing landed, to produce a string nobody
reads twice.
"""

from __future__ import annotations

import re

_WHITESPACE = re.compile(r"\s+")
_SENTENCE_END = re.compile(r"(?<=[.!?])\s")
MAX_LENGTH = 72


def derive_title(text: str, *, max_length: int = MAX_LENGTH) -> str | None:
    """First sentence, or a clean truncation. None when there is nothing to title."""
    cleaned = _WHITESPACE.sub(" ", (text or "").strip())
    if not cleaned:
        return None

    first = _SENTENCE_END.split(cleaned, maxsplit=1)[0].strip()
    candidate = first or cleaned
    if len(candidate) <= max_length:
        return candidate.rstrip(".")

    # Truncate on a word boundary rather than mid-word; fall back to a hard cut
    # for text with no spaces at all.
    clipped = candidate[:max_length]
    spaced = clipped.rsplit(" ", 1)[0]
    return (spaced if len(spaced) >= max_length // 2 else clipped).rstrip(" .,;:") + "…"
