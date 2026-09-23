#!/usr/bin/env python3
"""Every gate, in order, as one command.

    python3 scripts/gate.py

This is the only definition of the gate set. CI runs this file; it does not
restate the steps. A workflow that listed its own commands would drift from the
ones a developer runs, and the two would disagree on the one day it mattered.

Stops at the first failing gate and exits with that gate's own exit code, so a
caller can tell a privacy failure from a type error without reading the log.

The order is deliberate. The airlock and redaction tests run first: they are
the fastest and the most important, and a build that leaks should not wait
behind a browser. The repository checks come next because they are nearly free.
The browser test runs after the build it needs, and the mutation check runs
last because it re-runs gates that must already be green to mean anything.

Each gate runs with an explicit working directory rather than a changed one,
so the script behaves the same from anywhere — including a timer hours later.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
API = ROOT / "apps/api"
WEB = ROOT / "apps/web"
PYTHON = os.environ.get("GATE_PYTHON", str(API / ".venv/bin/python"))

PYTEST = [PYTHON, "-m", "pytest", "-q", "-p", "no:cacheprovider"]

GATES: list[tuple[str, list[str]]] = [
    ("airlock", PYTEST + [str(API / "tests/test_profile_airlock.py"),
                          str(API / "tests/test_redaction.py"),
                          str(API / "tests/test_research.py")]),
    ("no environment details", ["bash", str(ROOT / "scripts/check-no-environment.sh")]),
    ("American English", ["bash", str(ROOT / "scripts/check-american-english.sh")]),
    # Beside the other two repository guards, and nearly as cheap. It checks the
    # claims a machine can check; the ones it cannot are named in its own output
    # so a green row is not read as "the documents agree".
    ("drift", [sys.executable, str(ROOT / "scripts/check-drift.py")]),
    ("specs", ["openspec", "validate", "--all", "--strict", "--no-interactive"]),
    ("api", PYTEST + [str(API / "tests")]),
    ("web unit", ["npm", "--prefix", str(WEB), "test"]),
    ("web types", ["npm", "--prefix", str(WEB), "run", "typecheck"]),
    # Built from clean, every time. On 21 Sep the browser gate spent a day
    # testing a chunk that did not match its source: a warm `.next/cache`
    # re-emitted the playhead's transform in its pre-fix form — percentages of
    # a one-pixel element — while `Scrubber.tsx` on disk had said pixels since
    # 2 Sep. Five browser tests passed against bytes nobody had written. The
    # browser gate exists precisely to answer "what does the browser actually
    # get", and a build cache is the one thing that can make that answer stale.
    # Measured cost of not trusting it: 16.2s warm against 19.9s clean.
    ("web build", ["npm", "--prefix", str(WEB), "run", "build:clean"]),
    ("browser", ["npm", "--prefix", str(WEB), "run", "e2e"]),
    ("mutations", [sys.executable, str(ROOT / "scripts/check-mutations.py")]),
]


def preflight() -> str | None:
    """What is missing, said up front rather than as a gate's stack trace."""
    if not Path(PYTHON).exists():
        return (f"no interpreter at {PYTHON}: create apps/api/.venv as "
                "docs/development/GATES.md describes, or set GATE_PYTHON")
    for tool in ("npm", "git", "openspec"):
        if shutil.which(tool) is None:
            return f"`{tool}` is not on PATH; see docs/development/GATES.md"
    if not (WEB / "node_modules").is_dir():
        return "apps/web/node_modules is missing: run `npm --prefix apps/web ci`"
    return None


def main() -> int:
    missing = preflight()
    if missing:
        print(f"gate: cannot start — {missing}", file=sys.stderr)
        return 2

    started = time.monotonic()
    for name, command in GATES:
        began = time.monotonic()
        print(f"gate: {name} …", flush=True)
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
        took = time.monotonic() - began
        if result.returncode != 0:
            print(result.stdout[-6000:], end="")
            print(result.stderr[-6000:], end="", file=sys.stderr)
            print(f"gate: {name} FAILED (exit {result.returncode}, {took:.1f}s)", file=sys.stderr)
            return result.returncode
        print(f"gate: {name} passed ({took:.1f}s)", flush=True)
    print(f"gate: all {len(GATES)} gates passed ({time.monotonic() - started:.1f}s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
