#!/usr/bin/env python3
"""Prove the gates can fail.

A test that has never failed is a hypothesis. Each mutation below reintroduces a
defect this project has actually shipped or nearly shipped, runs the one gate
that exists to catch it, and requires that gate to go red. The file is then
restored from the bytes read before mutating — never from git, so an
uncommitted change is never discarded.

A mutation whose `before` text no longer appears exactly once is a failure, not
a skip. Code moves, and a mutation that silently stopped applying would report
"caught" for a defect it no longer introduces.

Run from anywhere: `python3 scripts/check-mutations.py [name ...]`.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PYTHON = os.environ.get("SECOND_SHIFT_PYTHON", str(ROOT / "apps/api/.venv/bin/python"))

WEB_TESTS = ["npm", "--prefix", str(ROOT / "apps/web"), "test"]
PYTEST = [PYTHON, "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider"]


@dataclass(frozen=True)
class Mutation:
    name: str
    why: str
    path: str
    before: str
    after: str
    gate: list[str]


MUTATIONS = [
    Mutation(
        "frame-ends-at-last-start",
        "2 Sep: a bar beginning near the end of the night overran its own frame.",
        "apps/web/lib/timeline.ts",
        "(latest, e) => Math.max(latest, e.ts_ms + (e.duration_ms ?? 0)),",
        "(latest, e) => Math.max(latest, e.ts_ms),",
        WEB_TESTS,
    ),
    Mutation(
        "no-minimum-bar-width",
        "2 Sep: a short bar rendered narrower than the tick it must be told apart from.",
        "apps/web/lib/timeline.ts",
        "w: bar ? Math.max(MIN_BAR_FRACTION, (event.duration_ms as number) / span) : 0,",
        "w: bar ? (event.duration_ms as number) / span : 0,",
        WEB_TESTS,
    ),
    Mutation(
        "lanes-by-joining",
        "2 Sep: lanes computed from events with an invocation passed a fixture in "
        "which every lane happened to have one, and dropped the night's skeleton.",
        "apps/web/lib/timeline.ts",
        "const lanes = timeline.lanes.length\n    ? timeline.lanes\n"
        "    : [...new Set(events.map((e) => e.lane))].sort();",
        "const lanes = [...new Set(events.filter((e) => e.agent_invocation_id)"
        ".map((e) => e.lane))].sort();",
        WEB_TESTS,
    ),
    Mutation(
        "stages-dropped",
        "2 Sep: a night that stopped part-way must say so, and says so from its stages.",
        "apps/web/lib/timeline.ts",
        "stages: timeline.stages,",
        "stages: [],",
        WEB_TESTS,
    ),
    Mutation(
        "playhead-percentage-transform",
        "2 Sep: the playhead moved by a percentage of its own one-pixel width and sat "
        "still while three ARIA-reading tests passed.",
        "apps/web/components/scrubber/Scrubber.tsx",
        "headRef.current.style.transform = `translateX(${position * width}px)`;",
        "headRef.current.style.transform = `translateX(${position * 100}%)`;",
        ["bash", "-c", f"npm --prefix '{ROOT}/apps/web' run build >/dev/null && "
         f"npm --prefix '{ROOT}/apps/web' run e2e"],
    ),
    Mutation(
        "answers-cross-ideas",
        "16 Sep: queued answers were taken by whichever entry ran first, carrying a "
        "local-only answer into a cloud-assisted run.",
        "apps/api/secondshift/morning/interview.py",
        '"SELECT * FROM decisions WHERE entry_id = ? AND status = \'queued-for-tonight\' "',
        '"SELECT * FROM decisions WHERE (entry_id = ? OR 1) AND status = \'queued-for-tonight\' "',
        PYTEST + [str(ROOT / "apps/api/tests/test_the_loop_closes.py")],
    ),
    Mutation(
        "identifiers-reach-the-query",
        "16 Sep: paths, assignments and mixed-case keys reached the search query.",
        "apps/api/secondshift/airlock/redact.py",
        '_IDENTIFIER_SHAPED = re.compile(r"[\\d_/\\\\=]|[a-z][A-Z]|^[A-Za-z-]{20,}$")',
        '_IDENTIFIER_SHAPED = re.compile(r"(?!)")',
        PYTEST + [str(ROOT / "apps/api/tests/test_redaction.py")],
    ),
    Mutation(
        "failure-loses-its-run",
        "16 Sep: stage failures recorded outside an invocation had no run, so the "
        "morning never said why a stage failed.",
        "apps/api/secondshift/telemetry/recorder.py",
        "run_id=run_id or (active.run_id if active else None),\n"
        "                agent_invocation_id=active.invocation_id if active else None,\n"
        "                is_synthetic=is_synthetic,\n            )\n\n    # --",
        "run_id=active.run_id if active else None,\n"
        "                agent_invocation_id=active.invocation_id if active else None,\n"
        "                is_synthetic=is_synthetic,\n            )\n\n    # --",
        PYTEST + [str(ROOT / "apps/api/tests/test_the_loop_closes.py")],
    ),
]


def run(mutation: Mutation) -> bool:
    path = ROOT / mutation.path
    original = path.read_bytes()
    text = original.decode()
    found = text.count(mutation.before)
    if found != 1:
        print(f"FAIL  {mutation.name}: its target appears {found} times in "
              f"{mutation.path} — the code moved; update the mutation")
        return False
    started = time.monotonic()
    try:
        path.write_text(text.replace(mutation.before, mutation.after, 1))
        result = subprocess.run(mutation.gate, cwd=ROOT, capture_output=True, text=True)
    finally:
        path.write_bytes(original)
    elapsed = time.monotonic() - started
    if result.returncode == 0:
        print(f"FAIL  {mutation.name}: the gate stayed green ({elapsed:.1f}s)\n      {mutation.why}")
        return False
    print(f"ok    {mutation.name}: caught ({elapsed:.1f}s)")
    return True


def main(names: list[str]) -> int:
    selected = [m for m in MUTATIONS if not names or m.name in names]
    unknown = set(names) - {m.name for m in MUTATIONS}
    if unknown:
        print(f"unknown mutation(s): {', '.join(sorted(unknown))}", file=sys.stderr)
        return 2
    results = [run(m) for m in selected]
    missed = results.count(False)
    print(f"{len(results) - missed} of {len(results)} mutations caught")
    return 1 if missed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
