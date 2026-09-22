"""Owning the machine.

    python -m secondshift.ops backup  --to <dir>      # a copy, with its evidence
    python -m secondshift.ops verify  <backup>        # is that copy still good
    python -m secondshift.ops restore <backup>        # put it back
    python -m secondshift.ops doctor  --backups <dir> # is this machine well

`backup` has no default destination. A default is how a copy of every captured
idea ends up somewhere nobody chose, and this archive is the most sensitive
thing the project produces.
"""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Sequence
from pathlib import Path

from .. import config
from .backup import CONTAINS, BackupRefused, Manifest, create_backup
from .doctor import run_checks
from .restore import restore_backup, verify_backup


def _paths(args) -> tuple[Path, Path]:
    """The database and artifacts this machine is configured to use.

    Read through `config.resolve_all` rather than from the environment
    directly, so that `ops` and `python -m secondshift.config show` can never
    disagree about where the data is — which is the disagreement that makes a
    backup of the wrong database look successful.
    """
    rows = {r.setting.name: r.value for r in config.resolve_all(dict(os.environ))}
    db = Path(args.db or rows[config.ENV_DB])
    artifacts = Path(args.artifacts or rows[config.ENV_ARTIFACTS])
    return db, artifacts


def _stamp() -> str:
    from datetime import UTC, datetime

    return datetime.now(UTC).strftime("%Y-%m-%dT%H-%M-%SZ")


def _backup(args) -> int:
    db, artifacts = _paths(args)
    destination = Path(args.to) / _stamp()
    manifest = create_backup(
        db_path=db,
        artifacts_root=artifacts,
        destination=destination,
        same_device_ok=args.same_device_ok,
    )
    rows = sum(manifest.tables.values())
    print(f"wrote {destination}")
    print(f"  database    {rows} rows across {len(manifest.tables)} tables, schema {manifest.schema_version}")
    print(f"  artifacts   {manifest.artifact_files} files, {manifest.artifact_bytes} bytes")
    for name, reason in sorted(manifest.excluded.items()):
        print(f"  excluded    {name} — {reason}")
    print(f"\n{CONTAINS}")
    return 0


def _verify(args) -> int:
    problems = verify_backup(Path(args.backup))
    if problems:
        print(f"{args.backup} does not match its manifest:", file=sys.stderr)
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        return 1
    manifest = Manifest.from_json((Path(args.backup) / "manifest.json").read_text())
    print(f"{args.backup} is intact: {len(manifest.members)} members, schema {manifest.schema_version}")
    return 0


def _restore(args) -> int:
    db, artifacts = _paths(args)
    manifest = restore_backup(
        source=Path(args.backup),
        db_path=db,
        artifacts_root=artifacts,
        overwrite=args.overwrite,
    )
    rows = sum(manifest.tables.values())
    print(f"restored {rows} rows across {len(manifest.tables)} tables to {db}")
    print(f"restored {manifest.artifact_files} artifact files to {artifacts}")
    print("checked against the manifest: every count and the schema version agree")
    return 0


def _doctor(args) -> int:
    checks = run_checks(backups=Path(args.backups) if args.backups else None)
    width = max(len(c.name) for c in checks)
    for check in checks:
        print(f"{'ok  ' if check.ok else 'FAIL'}  {check.name:<{width}}  {check.detail}")
    failed = [c for c in checks if not c.ok]
    if failed:
        print(f"\n{len(failed)} of {len(checks)} checks failed", file=sys.stderr)
        return 1
    print(f"\nall {len(checks)} checks passed")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m secondshift.ops")
    parser.add_argument("--db", help="override the configured database path")
    parser.add_argument("--artifacts", help="override the configured artifacts path")
    sub = parser.add_subparsers(dest="command", required=True)

    take = sub.add_parser("backup", help="write a copy, with the evidence to check it")
    take.add_argument(
        "--to",
        required=True,
        help="where the backup goes. Required, and there is no default.",
    )
    take.add_argument(
        "--same-device-ok",
        action="store_true",
        help=(
            "write to the same disk as the database. For a rehearsal; a real "
            "backup there would be lost with the original."
        ),
    )
    take.set_defaults(fn=_backup)

    check = sub.add_parser("verify", help="check a backup against its own manifest")
    check.add_argument("backup")
    check.set_defaults(fn=_verify)

    put = sub.add_parser("restore", help="put a backup back")
    put.add_argument("backup")
    put.add_argument(
        "--overwrite",
        action="store_true",
        help="replace an existing database. Without this, an occupied path refuses.",
    )
    put.set_defaults(fn=_restore)

    well = sub.add_parser("doctor", help="is this machine well")
    well.add_argument("--backups", help="the directory backups are written to")
    well.set_defaults(fn=_doctor)

    args = parser.parse_args(argv)
    try:
        return args.fn(args)
    except BackupRefused as exc:
        # Refusals are the feature. They print as the reason they happened, not
        # as a traceback with the reason buried in it.
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
