#!/usr/bin/env python3
"""Refuse to ship a database that should never reach a judge deployment.

`model_call_payloads` is how raw, unredacted prompt and completion text for
local-only ideas is reached. The schema says it "must never be synced,
uploaded, or included in a judge deployment", and that was a SQL comment with
nothing behind it — a sentence somebody wrote hoping a later reader would obey
it.

**The rows are pointers, not the text.** `prompt_path` and `completion_path`
name files under `data/payloads/`, and that is where the content actually is.
So this refuses a database that carries the rows, and the image must
additionally not copy those files — a build that enumerates what it includes,
rather than excluding what it must not, is the only version of that which stays
correct. The rows are still worth refusing: they are an index of what the
subject thought about and when.

The judge image bakes a database in, which is the one path where this can go
wrong: build it against the wrong file and the subject's unredacted thinking
ships to a public endpoint. The Spark deploy is not that path — it ships code
only, no database and no brain — so this is not wired there.

Also refuses a database holding any row a judge deployment has no business
carrying: a real entry is real data whether or not a payload came with it, and
principle 5 says the judge instance contains zero of it.

    python3 scripts/check-judge-package.py <database>

Exits 0 when the file is safe to ship, 1 when it is not, naming what it found.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

#: Tables that must hold nothing at all, whatever it is marked.
_FORBIDDEN_TABLES = ("model_call_payloads",)

#: Tables where every row must be marked synthetic. Read from the schema rather
#: than listed, so a table added by a later migration is checked the day it
#: appears — the same discovery the synthetic audit already uses.
_SKIP = frozenset({"schema_version", "agents", "run_stages", "eval_prompts"})


def _flagged_tables(conn: sqlite3.Connection) -> list[str]:
    names = [
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        )
    ]
    return [
        name
        for name in names
        if name not in _SKIP
        and any(
            column[1] == "is_synthetic"
            for column in conn.execute(f"PRAGMA table_info({name})")
        )
    ]


def problems(path: Path) -> list[str]:
    """Everything wrong with this database as a judge package. Empty is safe."""
    found: list[str] = []
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        present = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        for table in _FORBIDDEN_TABLES:
            if table not in present:
                continue
            count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            if count:
                found.append(
                    f"{table} holds {count} row(s) of raw local-only content, "
                    "which must never reach a judge deployment"
                )

        for table in _flagged_tables(conn):
            real = conn.execute(
                f"SELECT COUNT(*) FROM {table} WHERE is_synthetic = 0"
            ).fetchone()[0]
            if real:
                found.append(f"{table} holds {real} unmarked (real) row(s)")
    finally:
        conn.close()
    return found


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__.strip().splitlines()[-3].strip(), file=sys.stderr)
        return 2
    path = Path(argv[1])
    if not path.is_file():
        print(f"no database at {path}", file=sys.stderr)
        return 2

    found = problems(path)
    if found:
        print(f"refusing to ship {path} to a judge deployment:", file=sys.stderr)
        for problem in found:
            print(f"  - {problem}", file=sys.stderr)
        return 1
    print(f"clean: {path} carries nothing a judge deployment must not hold")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
