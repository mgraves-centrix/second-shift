"""Sync the brain from the command line and from a timer.

    python -m secondshift.brain            # journal and commit
    python -m secondshift.brain --status   # how far behind is it?

Deliberately a separate entry point rather than an API route: journaling is not
request work, and giving it a URL would invite exactly that.
"""

from __future__ import annotations

import argparse
import os
import sys

from ..db.connection import connect
from ..db.migrate import migrate
from ..db.repository import Repository
from .repo import BrainRepo, BrainUnavailable
from .sync import backlog, sync

DEFAULT_DB = os.path.expanduser("~/second-shift-data/second-shift.db")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="secondshift.brain")
    parser.add_argument("--db", default=os.environ.get("SECOND_SHIFT_DB", DEFAULT_DB))
    parser.add_argument("--brain", default=None, help="brain repository path")
    parser.add_argument("--status", action="store_true", help="report backlog and exit")
    args = parser.parse_args(argv)

    conn = connect(args.db)
    migrate(conn)
    repo = Repository(conn)
    brain = BrainRepo(args.brain)

    if args.status:
        pending = backlog(repo, brain)
        if pending < 0:
            print(f"brain unavailable at {brain.path}", file=sys.stderr)
            return 1
        print(f"{pending} entries not yet journaled; brain at {brain.head() or 'unknown'}")
        return 0

    try:
        result = sync(repo, brain)
    except BrainUnavailable as exc:
        # Loud. A brain silently not written looks identical to a brain with
        # nothing to write, right up until the eight-week diff is empty.
        print(f"brain sync failed: {exc}", file=sys.stderr)
        return 1

    if result.count == 0:
        print("nothing to journal" + (f"; committed {result.commit[:8]}" if result.commit else ""))
    else:
        print(
            f"journaled {result.count} "
            f"{'entry' if result.count == 1 else 'entries'} "
            f"({', '.join(result.dates)})"
            + (f"; commit {result.commit[:8]}" if result.commit else "")
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
