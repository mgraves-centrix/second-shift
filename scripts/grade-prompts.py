"""Grade the session prompts in docs/prompts/ against the rubric in 00_INDEX.md.

Run it; do not trust a grade that was claimed rather than computed.

    python3 scripts/grade-prompts.py

Text is normalized before matching, because a criterion that a line break can
defeat is a criterion that measures formatting. Two of these checks originally
did exactly that and reported false failures against prose that satisfied them.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

PROMPTS = Path(__file__).resolve().parents[1] / "docs" / "prompts"

#: Not prompts. The first three set the bar rather than being measured against
#: it; the last two describe the set. Grading the report card is how this script
#: first reported a failure against itself.
NOT_PROMPTS = {
    "00_INDEX.md",
    "OVERNIGHT.md",
    "NIGHT_SCRUBBER.md",
    "GRADES.md",
}

CRITERIA: dict[str, tuple[str, object]] = {
    "1": ("grounded in verified fact", lambda t: "do not invent any of it" in t),
    "2": ("reproduction commands", lambda t: t.count("```bash") >= 1),
    "3": ("names the open decision", lambda t: "the open decision" in t),
    "4": ("forbids deciding by preference", lambda t: "by preference" in t),
    "5": ("falsifiable success criteria", lambda t: "what good looks like" in t),
    "6": ("explicit non-goals", lambda t: "not to build" in t),
    "7": ("constitution hooks", lambda t: "constitution hooks" in t),
    "8": ("a runnable loop", lambda t: "## the loop" in t and "pytest" in t),
    "9": ("verification that can fail",
          lambda t: re.search(r"(able to fail|can fail|must be able|go red)", t) is not None),
    "10": ("quality bar", lambda t: "never ship" in t and "always:" in t),
    "11": ("hard stops",
           lambda t: "hard stops" in t and "needs clarification" in t),
    "12": ("report demands honesty",
           lambda t: re.search(r"(say so|honestly)", t) is not None),
}

PASS_MARK = 11.9


def normalize(text: str) -> str:
    """Collapse whitespace and lower-case, so a line break cannot fail a check."""
    return re.sub(r"\s+", " ", text).lower()


def main() -> int:
    files = sorted(p for p in PROMPTS.glob("*.md") if p.name not in NOT_PROMPTS)
    if not files:
        print(f"no prompts found in {PROMPTS}", file=sys.stderr)
        return 2

    failed: list[tuple[str, list[str]]] = []
    width = max(len(p.name) for p in files)
    print(f"{'prompt':<{width}} " + " ".join(f"{k:>3}" for k in CRITERIA) + "   score")

    for path in files:
        text = normalize(path.read_text())
        marks = {k: bool(check(text)) for k, (_, check) in CRITERIA.items()}
        score = sum(marks.values())
        misses = [f"{k} ({CRITERIA[k][0]})" for k, ok in marks.items() if not ok]
        if score < PASS_MARK:
            failed.append((path.name, misses))
        row = " ".join(("  ." if ok else "  X") for ok in marks.values())
        print(f"{path.name:<{width}} {row}   {score}/12")

    print()
    if failed:
        print(f"below {PASS_MARK}:")
        for name, misses in failed:
            print(f"  {name}: missing {', '.join(misses)}")
        return 1
    print(f"all {len(files)} prompts at 12/12")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
