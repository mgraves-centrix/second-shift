"""Taking a copy of the data that only exists on one machine.

The database is copied through SQLite's own online backup API and never by
copying the file. It runs in write-ahead logging mode, so committed
transactions — including `CREATE TABLE` — live in the `-wal` file until a
checkpoint moves them, and a checkpoint is not guaranteed to have happened at
any particular moment. Copying `second-shift.db` alone after five hundred
committed inserts produces a database in which the table does not exist. That
failure restores cleanly and presents an empty database, which is the worst
available shape: it looks like a successful recovery of a machine that had
nothing on it. `test_operations.py` keeps the demonstration.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
from dataclasses import asdict, dataclass, field
from pathlib import Path

from ..db.connection import connect, now_ms
from ..db.migrate import current_version

#: The database, under this name, inside a backup.
DATABASE = "second-shift.db"

#: The artifacts tree, under this name, inside a backup.
ARTIFACTS = "artifacts"

#: What a backup records about itself.
MANIFEST = "manifest.json"

#: Named in every manifest rather than silently absent. An operator who reads a
#: manifest and does not see the brain should learn that it is covered
#: elsewhere, not conclude from silence that it was included.
EXCLUDED = {
    "brain": (
        "a git repository with its own mirror; Principle 1 says a copy is a "
        "clone, never the original, and two backup systems disagreeing about "
        "which is authoritative is worse than the failure they prevent"
    ),
    "deployed tree": "reproducible from git; deploy.sh destroys and recreates it",
}

#: Printed every time a backup is written. The sensitivity of the artifact
#: belongs at the moment somebody decides where to put it, not in a document
#: they read once.
CONTAINS = (
    "this archive holds unredacted captured text and every recorded model "
    "payload; it must not leave the boundary that holds the brain"
)


class BackupRefused(RuntimeError):
    """A backup or restore that would destroy or invent something."""


@dataclass(frozen=True)
class Member:
    """One file inside a backup, and the digest that proves it is intact."""

    path: str
    bytes: int
    sha256: str


@dataclass(frozen=True)
class Manifest:
    """What a backup contains, in enough detail to check a restore against it.

    Counts and the schema version come from the *copy*, not from the source.
    The manifest is evidence about the backup, and reading them from the copy
    also proves it opens — a manifest describing a source it never re-read
    would be describing a file it cannot vouch for.
    """

    taken_at_ms: int
    schema_version: int
    tables: dict[str, int]
    artifact_files: int
    artifact_bytes: int
    members: list[Member]
    excluded: dict[str, str] = field(default_factory=lambda: dict(EXCLUDED))

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=True) + "\n"

    @classmethod
    def from_json(cls, text: str) -> Manifest:
        raw = json.loads(text)
        return cls(
            taken_at_ms=raw["taken_at_ms"],
            schema_version=raw["schema_version"],
            tables=raw["tables"],
            artifact_files=raw["artifact_files"],
            artifact_bytes=raw["artifact_bytes"],
            members=[Member(**m) for m in raw["members"]],
            excluded=raw.get("excluded", {}),
        )


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def table_counts(conn: sqlite3.Connection) -> dict[str, int]:
    """Every table's row count, enumerated from the database rather than listed.

    A hard-coded list of tables is a list that a migration adds to and nobody
    updates, and the manifest would then verify a restore of the tables somebody
    remembered.
    """
    names = [
        row["name"]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' "
            "AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )
    ]
    return {name: conn.execute(f"SELECT count(*) AS n FROM '{name}'").fetchone()["n"] for name in names}


def create_backup(
    *,
    db_path: Path,
    artifacts_root: Path,
    destination: Path,
) -> Manifest:
    """Write a consistent copy of the database and the artifacts to `destination`.

    `destination` must not already hold a backup. There is no default for it
    anywhere in this package: a default destination is how a copy of every
    captured idea ends up somewhere nobody chose.
    """
    if not db_path.exists():
        raise BackupRefused(f"no database at {db_path}")
    if (destination / MANIFEST).exists():
        raise BackupRefused(
            f"{destination} already holds a backup taken at "
            f"{Manifest.from_json((destination / MANIFEST).read_text()).taken_at_ms}"
        )

    destination.mkdir(parents=True, exist_ok=True)
    copied_db = destination / DATABASE

    source = connect(db_path)
    try:
        target = sqlite3.connect(str(copied_db))
        try:
            # Page by page, restarting any page a writer changes mid-copy. The
            # one mechanism demonstrated correct while something else is
            # writing, which is the only condition that matters at 2am.
            source.backup(target)
            target.row_factory = sqlite3.Row
            counts = table_counts(target)
            version = current_version(target)
        finally:
            target.close()
    finally:
        source.close()

    artifact_files, artifact_bytes = _copy_artifacts(artifacts_root, destination / ARTIFACTS)

    members = [
        Member(path=str(p.relative_to(destination)), bytes=p.stat().st_size, sha256=digest(p))
        for p in sorted(destination.rglob("*"))
        if p.is_file() and p.name != MANIFEST
    ]
    manifest = Manifest(
        taken_at_ms=now_ms(),
        schema_version=version,
        tables=counts,
        artifact_files=artifact_files,
        artifact_bytes=artifact_bytes,
        members=members,
    )
    (destination / MANIFEST).write_text(manifest.to_json())
    return manifest


def _copy_artifacts(root: Path, destination: Path) -> tuple[int, int]:
    """Ordinary files that nothing holds open, so an ordinary copy is correct.

    A missing root is not an error. A machine that has never run a night has no
    artifacts, and refusing to back up its database over that would be refusing
    the case where a backup matters most.
    """
    if not root.is_dir():
        destination.mkdir(parents=True, exist_ok=True)
        return 0, 0
    shutil.copytree(root, destination, dirs_exist_ok=True)
    files = [p for p in destination.rglob("*") if p.is_file()]
    return len(files), sum(p.stat().st_size for p in files)
