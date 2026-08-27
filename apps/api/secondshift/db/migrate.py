"""Forward-only migrations.

Numbered SQL files applied in order against a `schema_version` table. No ORM,
no migration framework, no down-migrations: at this scale a migration tool is
more moving parts than the thing it manages, and rollback during the
pre-dogfooding window is a fresh database.
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from .connection import now_ms

MIGRATIONS_DIR = Path(__file__).parent / "migrations"
_FILENAME = re.compile(r"^(\d{4})_([a-z0-9_]+)\.sql$")

_SCHEMA_VERSION_DDL = """
CREATE TABLE IF NOT EXISTS schema_version (
  version     INTEGER PRIMARY KEY,
  name        TEXT    NOT NULL,
  applied_at_ms INTEGER NOT NULL
)
"""


@dataclass(frozen=True)
class Migration:
    version: int
    name: str
    path: Path

    def sql(self) -> str:
        return self.path.read_text()


def discover(directory: Path | None = None) -> list[Migration]:
    """Return every migration on disk, ordered by version.

    A file that does not match `NNNN_name.sql` is an error rather than an
    oversight: silently skipping it would apply a partial schema.
    """
    directory = directory or MIGRATIONS_DIR
    found: list[Migration] = []
    for path in sorted(directory.glob("*.sql")):
        match = _FILENAME.match(path.name)
        if not match:
            raise ValueError(
                f"migration filename must be NNNN_name.sql, got {path.name!r}"
            )
        found.append(Migration(int(match.group(1)), match.group(2), path))

    versions = [m.version for m in found]
    if len(set(versions)) != len(versions):
        raise ValueError(f"duplicate migration versions: {versions}")
    return found


def current_version(conn: sqlite3.Connection) -> int:
    """Highest applied version, or 0 for a database with no migrations yet."""
    conn.execute(_SCHEMA_VERSION_DDL)
    row = conn.execute("SELECT MAX(version) AS v FROM schema_version").fetchone()
    return row["v"] or 0


def migrate(conn: sqlite3.Connection, directory: Path | None = None) -> list[int]:
    """Apply every migration newer than the current version.

    Returns the versions applied, empty when the database is already current.
    Each migration commits with its own version row, so an interrupted run
    leaves the database at a known version rather than half-applied.
    """
    applied: list[int] = []
    version = current_version(conn)

    for migration in discover(directory):
        if migration.version <= version:
            continue
        # executescript() implicitly commits any open transaction, so the
        # version row is appended to the script rather than issued separately.
        # Either the whole migration lands or none of it does; a crash cannot
        # leave a schema applied but unrecorded.
        script = (
            "BEGIN;\n"
            + migration.sql()
            + "\nINSERT INTO schema_version (version, name, applied_at_ms) "
            + f"VALUES ({migration.version}, '{migration.name}', {now_ms()});\n"
            + "COMMIT;\n"
        )
        try:
            conn.executescript(script)
        except BaseException:
            conn.executescript("ROLLBACK;")
            raise
        applied.append(migration.version)

    return applied
