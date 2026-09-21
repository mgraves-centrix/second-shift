"""Checking a copy, and putting it back.

`verify` exists so that checking a backup does not require trusting one. A
backup nobody has restored is a hypothesis, and restoring it to find out is the
one test you cannot run on the day you need it.
"""

from __future__ import annotations

import shutil
import sqlite3
from pathlib import Path

from ..db.connection import connect
from ..db.migrate import current_version
from .backup import (
    ARTIFACTS,
    DATABASE,
    MANIFEST,
    BackupRefused,
    Manifest,
    digest,
    table_counts,
)


def verify_backup(path: Path) -> list[str]:
    """Every disagreement between a backup and its own manifest.

    Returns problems rather than raising on the first, because an operator
    deciding whether a backup is usable wants to know how bad it is, not what
    broke first.
    """
    manifest_path = path / MANIFEST
    if not manifest_path.exists():
        return [f"{path} holds no manifest, so nothing about it can be checked"]

    manifest = Manifest.from_json(manifest_path.read_text())
    problems: list[str] = []

    recorded = {m.path for m in manifest.members}
    on_disk = {
        str(p.relative_to(path))
        for p in path.rglob("*")
        if p.is_file() and p.name != MANIFEST
    }
    for extra in sorted(on_disk - recorded):
        problems.append(f"{extra} is in the backup and not in its manifest")

    database_intact = False
    for member in manifest.members:
        member_path = path / member.path
        if not member_path.exists():
            problems.append(f"{member.path} is recorded and missing")
            continue
        size = member_path.stat().st_size
        if size != member.bytes:
            problems.append(f"{member.path} is {size} bytes, recorded as {member.bytes}")
            continue
        if digest(member_path) != member.sha256:
            problems.append(f"{member.path} does not match its recorded digest")
            continue
        database_intact = database_intact or member.path == DATABASE

    # Only when the bytes are already known good. Opening a database whose
    # digest disagrees would report whatever the damage happens to look like,
    # on top of the one problem worth reporting.
    if database_intact:
        problems.extend(_check_database(path / DATABASE, manifest))
    elif not any(m.path == DATABASE for m in manifest.members):
        problems.append(f"the manifest records no {DATABASE}")
    return problems


def _check_database(database: Path, manifest: Manifest) -> list[str]:
    conn = sqlite3.connect(str(database))
    conn.row_factory = sqlite3.Row
    try:
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            return [f"the database fails integrity_check: {integrity}"]
        return _disagreements(table_counts(conn), current_version(conn), manifest)
    except sqlite3.DatabaseError as exc:
        return [f"the database will not open: {exc}"]
    finally:
        conn.close()


def _disagreements(counts: dict[str, int], version: int, manifest: Manifest) -> list[str]:
    problems = []
    if version != manifest.schema_version:
        problems.append(
            f"schema version {version}, recorded as {manifest.schema_version}"
        )
    for table, expected in sorted(manifest.tables.items()):
        actual = counts.get(table)
        if actual is None:
            problems.append(f"table {table} is recorded and absent")
        elif actual != expected:
            problems.append(f"{table} holds {actual} rows, recorded as {expected}")
    for table in sorted(set(counts) - set(manifest.tables)):
        problems.append(f"table {table} is present and not recorded")
    return problems


def restore_backup(
    *,
    source: Path,
    db_path: Path,
    artifacts_root: Path,
    overwrite: bool = False,
) -> Manifest:
    """Rebuild from a backup, then check the result against what was taken.

    Verified before anything is written. Restoring a damaged backup over a
    working database turns one problem into two, and the damage is knowable
    beforehand.
    """
    problems = verify_backup(source)
    if problems:
        raise BackupRefused(
            f"{source} does not match its manifest, so it is not being restored:\n  "
            + "\n  ".join(problems)
        )

    if db_path.exists() and not overwrite:
        raise BackupRefused(
            f"{db_path} already exists, holding {_describe(db_path)}. "
            "Restoring would replace it. Move it aside, or pass --overwrite "
            "to say that is what you meant."
        )

    manifest = Manifest.from_json((source / MANIFEST).read_text())

    db_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source / DATABASE, db_path)
    # The sidecars of whatever was there: a `-wal` left beside a database it
    # does not belong to is read as that database's committed tail.
    for sidecar in (f"{db_path}-wal", f"{db_path}-shm"):
        Path(sidecar).unlink(missing_ok=True)

    if artifacts_root.exists() and overwrite:
        shutil.rmtree(artifacts_root)
    if (source / ARTIFACTS).is_dir():
        shutil.copytree(source / ARTIFACTS, artifacts_root, dirs_exist_ok=True)

    written = connect(db_path)
    try:
        disagreements = _disagreements(
            table_counts(written), current_version(written), manifest
        )
    finally:
        written.close()
    if disagreements:
        raise BackupRefused(
            "the restored database does not match the manifest:\n  "
            + "\n  ".join(disagreements)
        )
    return manifest


def _describe(db_path: Path) -> str:
    """What is already there, so a refusal is informative rather than obstinate."""
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        try:
            counts = table_counts(conn)
        finally:
            conn.close()
    except sqlite3.DatabaseError:
        return f"{db_path.stat().st_size} bytes that do not open as a database"
    rows = sum(counts.values())
    return f"{len(counts)} tables and {rows} row{'' if rows == 1 else 's'}"
