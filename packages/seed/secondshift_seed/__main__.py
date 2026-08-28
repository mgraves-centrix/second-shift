"""Seed a database from the command line.

    python -m secondshift_seed --seed 7 --db ~/second-shift-data/second-shift.db

Deliberately not an API route. Seeding writes hundreds of rows under one
transaction and is something an operator does to a deployment, not something a
request does to a running night — and giving it a URL would put a "fill this
database with fake data" endpoint on the same surface that serves real capture.
"""

from __future__ import annotations

import argparse
import datetime as dt
import os

from secondshift.airlock.policy import Policy
from secondshift.db.connection import connect
from secondshift.db.migrate import migrate
from secondshift.db.repository import Repository

from .night import DEFAULT_NIGHT_OF, generate_night

DEFAULT_DB = os.path.expanduser("~/second-shift-data/second-shift.db")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="secondshift_seed",
        description="Write one deterministic synthetic night into a database.",
    )
    parser.add_argument(
        "--seed", type=int, required=True, help="the night is a function of this"
    )
    parser.add_argument("--db", default=os.environ.get("SECOND_SHIFT_DB", DEFAULT_DB))
    parser.add_argument(
        "--night-of", default=DEFAULT_NIGHT_OF, help="local date, YYYY-MM-DD"
    )
    parser.add_argument(
        "--policy",
        default=str(Policy.CLOUD_ASSISTED),
        choices=[str(Policy.LOCAL_ONLY), str(Policy.CLOUD_ASSISTED)],
    )
    parser.add_argument(
        "--profile", default="spark", choices=("spark", "workstation", "cloud")
    )
    args = parser.parse_args(argv)

    # Checked here rather than caught around the generator: `generate_night`
    # raises ValueError for genuine faults too, and reporting one of those as an
    # operator typo would hide it.
    try:
        dt.date.fromisoformat(args.night_of)
    except ValueError:
        parser.error(f"--night-of must be YYYY-MM-DD, got {args.night_of!r}")

    conn = connect(args.db)
    try:
        migrate(conn)
        night = generate_night(
            Repository(conn),
            seed=args.seed,
            night_of=args.night_of,
            policy=args.policy,
            compute_profile=args.profile,
        )
    finally:
        conn.close()

    print(
        f"seeded run {night.run_id} on {args.night_of} under {night.policy}: "
        f"{len(night.entry_ids)} entries, {len(night.invocation_ids)} invocations, "
        f"{len(night.model_call_ids)} model calls, "
        f"{len(night.tool_call_ids)} tool calls, "
        f"{len(night.failure_ids)} failures, {night.event_count} events"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
