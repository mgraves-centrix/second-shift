#!/usr/bin/env python3
"""Claims about this repository that a machine can check, checked every commit.

`docs/SPEC_ROADMAP.md` carries a table of twelve findings under "The drift pass
— 2 Sep", every one a claim in a document that had stopped being true. That pass
was done by hand, and so were the ones after it. The passes work; what they
cannot be is exhaustive, because their coverage is the memory of whoever is
looking. `docs/ARCHITECTURE.md` says it of itself, in the paragraph above its
own tree: it "was wrong for a week because nobody did".

**What this does not check is most of it.** It does not read prose for meaning,
compare a document against a document, or notice that a proposal promises
something its own design rejected ninety lines below — which was the sharpest
drift of the week it was written. A green run here means three specific things
were true, and it prints which three so that nobody reads it as more.

Nothing is inferred. A number is checked only where the prose states what it
derives from, because a checker that guesses produces false positives and a
check with false positives is one people learn to suppress.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

#: The document whose tree is checked, and the line its tree starts on.
TREE_DOC = ROOT / "docs/ARCHITECTURE.md"
TREE_ROOT = "second-shift/"

#: `├── name/   trailing prose   (planned)`
_ENTRY = re.compile(r"^((?:[│ ]   )*)(?:├──|└──) (\S+)(.*)$")

#: `<!-- derived: lines apps/api/secondshift/api/app.py -->`, preceded on the
#: same line by the number it claims. A third field, where the derivation takes
#: one, runs to the end of the marker so a pattern may contain spaces.
#: The number must be the one nearest the marker, so the gap between them
#: carries no digits. Without that, `python3 scripts/gate.py runs 11 gates
#: <!-- ... -->` reports the **3** in `python3` as the claim — which it did, on
#: the first real line this was pointed at.
_DERIVED = re.compile(
    r"(\d[\d,]*)(?:[^\d<\n]*?)<!--\s*derived:\s*(\w+)\s+(\S+)(?:\s+(.*?))?\s*-->"
)


def tree_entries(doc: Path) -> list[tuple[str, bool]]:
    """Every path the tree asserts, and whether it is marked planned."""
    lines = doc.read_text().splitlines()
    start = next(i for i, line in enumerate(lines) if line.strip() == TREE_ROOT)
    end = next(i for i in range(start, len(lines)) if lines[i].startswith("```"))

    stack: dict[int, str] = {}
    entries: list[tuple[str, bool]] = []
    for line in lines[start + 1 : end]:
        found = _ENTRY.match(line)
        if not found:
            continue
        depth = len(found.group(1)) // 4
        stack[depth] = found.group(2).rstrip("/")
        path = "/".join(stack[d] for d in range(depth + 1))
        entries.append((path, "(planned)" in found.group(3)))
    return entries


def check_tree() -> list[str]:
    """Both directions, and the second one is why this exists twice.

    The 16 Sep pass corrected this tree for asserting seven directories that did
    not exist. It left `night/` and `morning/` marked planned after both had
    shipped — the same tree, the opposite error, and a reader being told work
    remains that does not.
    """
    problems = []
    for path, planned in tree_entries(TREE_DOC):
        exists = (ROOT / path).exists()
        if planned and exists:
            problems.append(
                f"{TREE_DOC.name}: {path} is marked (planned) and exists"
            )
        elif not planned and not exists:
            problems.append(f"{TREE_DOC.name}: {path} is asserted and does not exist")
    return problems


def derive(kind: str, target: str, pattern: str = "") -> int:
    """The three shapes the stale claims in this repository have taken.

    `matches` is here because the claim that broke most often is a count of
    things inside a file — routes in a module, gates in the gate script, test
    functions in a suite — and none of those is a file you can count with a
    glob. Adding the drift gate itself made ten documents say "ten gates", which
    is the same failure one more time and the reason this shape exists.
    """
    if kind == "lines":
        return len((ROOT / target).read_text().splitlines())
    if kind == "count":
        return len(list(ROOT.glob(target)))
    if kind == "matches":
        if not pattern:
            raise ValueError("matches needs a pattern: `matches <path> <regex>`")
        return len(re.findall(pattern, (ROOT / target).read_text(), re.MULTILINE))
    raise ValueError(f"unknown derivation {kind!r}; known: lines, count, matches")


def check_derived(files: list[Path]) -> list[str]:
    """Numbers that say what they mean, checked against what they mean.

    A marker is the whole mechanism. An unmarked number is not reported and not
    guessed at: this repository's prose is full of real numbers that derive from
    nothing in it — five rubric dimensions, six night stages — and a checker
    that tried to tell them apart would be wrong often enough to be turned off.
    """
    problems = []
    for path in files:
        if not path.is_file():
            # `git ls-files` lists what the index holds, which during a rename
            # or a delete is not what is on disk. The first run of this gate
            # after an `openspec archive` crashed here rather than reporting,
            # and a tree mid-move is exactly when somebody runs the gate. A file
            # that is not there has no claims in it.
            continue
        for line_no, line in enumerate(path.read_text().splitlines(), 1):
            for claimed, kind, target, pattern in _DERIVED.findall(line):
                stated = int(claimed.replace(",", ""))
                try:
                    actual = derive(kind, target, pattern)
                except (OSError, ValueError) as exc:
                    problems.append(
                        f"{path.relative_to(ROOT)}:{line_no}: cannot derive "
                        f"{kind} {target}: {exc}"
                    )
                    continue
                if stated != actual:
                    problems.append(
                        f"{path.relative_to(ROOT)}:{line_no}: says {stated}, "
                        f"but {kind} {target} is {actual}"
                    )
    return problems


def check_bookkeeping() -> list[str]:
    """What the listings people read would say, against what is true.

    `nebius-executor` read "✓ Complete" in `openspec list` for three weeks with
    none of its work done, because its second task group was three sentences of
    prose rather than tasks. That listing is what somebody reads to decide what
    to do next.
    """
    problems = []
    changes = ROOT / "openspec/changes"
    for change in sorted(changes.glob("2026-*")):
        tasks = change / "tasks.md"
        if not tasks.is_file():
            problems.append(f"{change.name}: in flight with no tasks.md")
            continue
        text = tasks.read_text()
        if not re.search(r"^\s*- \[ \]", text, re.MULTILINE):
            problems.append(
                f"{change.name}: in flight with no unchecked task, so the "
                "listing reports it complete"
            )

    for spec in sorted((ROOT / "openspec/specs").iterdir()):
        if not spec.is_dir():
            continue
        if not list(changes.glob(f"archive/*/specs/{spec.name}")):
            problems.append(
                f"{spec.name}: canonical requirements with no archived change "
                "that added them"
            )
    return problems


def tracked_prose() -> list[Path]:
    """Tracked markdown, from git rather than a walk.

    A walk picks up `node_modules` and an archived checkout; `git ls-files` is
    the same list the repository guards already use.
    """
    listed = subprocess.run(
        ["git", "ls-files", "*.md"], cwd=ROOT, capture_output=True, text=True, check=True
    )
    return [ROOT / name for name in listed.stdout.split()]


def main() -> int:
    prose = tracked_prose()
    checks = (
        ("the documented tree against the filesystem, both directions", check_tree()),
        ("every number that says what it derives from", check_derived(prose)),
        ("change and spec bookkeeping", check_bookkeeping()),
    )

    problems = [p for _, found in checks for p in found]
    for problem in problems:
        print(problem, file=sys.stderr)
    if problems:
        print(
            f"\n{len(problems)} claim(s) in this repository are not true.",
            file=sys.stderr,
        )
        return 1

    print(f"checked, across {len(prose)} tracked documents:")
    for what, _ in checks:
        print(f"  {what}")
    # Said on success, not only in the source. A narrow check that passes is
    # read as a broad one unless it says otherwise, and the drift this misses is
    # the drift somebody still has to go and look for.
    print("\nNot checked: whether any two documents agree, or whether a document")
    print("agrees with itself. Those still need somebody to read them.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
