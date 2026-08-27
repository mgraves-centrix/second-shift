"""SQLite connection factory.

One writer. WAL mode so readers never block the night's writes, foreign keys
enforced so the invocation tree cannot be corrupted by an orphaned row, and a
row factory that returns mappings rather than positional tuples.
"""

from __future__ import annotations

import sqlite3
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


def now_ms() -> int:
    """Current time as epoch milliseconds, UTC.

    Every timestamp column in the schema is an INTEGER of this form. Local
    framing is carried separately on `entries`.
    """
    return int(time.time() * 1000)


def connect(path: str | Path) -> sqlite3.Connection:
    """Open a connection with the pragmas this schema requires."""
    # check_same_thread=False is required, not a shortcut: work handed to a
    # thread pool records its own telemetry, and out-of-process telemetry is
    # ingested through this same connection. sqlite3's thread check is a
    # redundant second guard over serialization that `Recorder` already owns
    # with a lock. Anything writing outside `Recorder` must hold that lock.
    conn = sqlite3.connect(str(path), isolation_level=None, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn


@contextmanager
def transaction(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    """Run a block in a single transaction, rolling back on any exception."""
    conn.execute("BEGIN")
    try:
        yield conn
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    conn.execute("COMMIT")
