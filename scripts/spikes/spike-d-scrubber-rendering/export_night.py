"""Export a generated night through the repository contract, for the harness.

Read through `Repository.timeline` and `Repository.invocation_tree` rather than
by hand-written SQL, so the measurement is against exactly the columns a renderer
will get — scalars only, no `payload_json`. A harness fed richer data than the
real contract provides would measure a renderer nobody can build.

    python scripts/spikes/spike-d-scrubber-rendering/export_night.py \
        --db /tmp/night.db --out /tmp/night.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from secondshift.db.connection import connect
from secondshift.db.repository import Repository


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--run", default="")
    args = parser.parse_args()

    conn = connect(args.db)
    try:
        repo = Repository(conn)
        run_id = args.run or conn.execute(
            "SELECT id FROM runs ORDER BY started_at_ms DESC LIMIT 1"
        ).fetchone()["id"]

        events = [dict(r) for r in repo.timeline(run_id)]
        invocations = [
            {
                "id": r["id"],
                "role": r["role"] if "role" in r.keys() else None,
                "depth": r["depth"],
                "parent_invocation_id": r["parent_invocation_id"],
            }
            for r in repo.invocation_tree(run_id)
        ]
    finally:
        conn.close()

    Path(args.out).write_text(
        json.dumps({"run_id": run_id, "events": events, "invocations": invocations})
    )
    print(f"{len(events)} events, {len(invocations)} invocations -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
