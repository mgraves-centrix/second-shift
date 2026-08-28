"""Journaling captured entries into the brain.

Never called from a request. Capture writes to SQLite and returns; this runs on
a timer and on demand, so the one interaction that must never fail does not
depend on a subprocess and a lock file.

Idempotent and interruptible by construction: what has been journaled is derived
from the journal, so a second run appends nothing and an interrupted run leaves
work the next one finishes.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..db.repository import Repository
from ..telemetry.recorder import Recorder
from .journal import JournalEntry, append_entries, journaled_ids
from .repo import JOURNAL_DIR, BrainRepo, BrainUnavailable


@dataclass(slots=True)
class SyncResult:
    journaled: list[str] = field(default_factory=list)
    commit: str | None = None
    dates: list[str] = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.journaled)


def unjournaled(repo: Repository, brain: BrainRepo) -> list[JournalEntry]:
    """Captured entries not yet in the journal, in capture order."""
    known = journaled_ids(brain.path)
    rows = repo.connection.execute(
        "SELECT id, created_at_ms, tz_offset_min, captured_tz, default_policy, "
        "raw_text, title FROM entries ORDER BY created_at_ms, id"
    ).fetchall()
    return [
        JournalEntry(
            entry_id=row["id"],
            created_at_ms=row["created_at_ms"],
            tz_offset_min=row["tz_offset_min"],
            captured_tz=row["captured_tz"],
            policy=row["default_policy"],
            text=row["raw_text"] or "",
            title=row["title"],
        )
        for row in rows
        if row["id"] not in known
    ]


def sync(repo: Repository, brain: BrainRepo, recorder: Recorder | None = None) -> SyncResult:
    """Append every unjournaled entry and commit the journal.

    Commits `journal/` alone, never the tree. A topic file edited by hand stays
    uncommitted and untouched — someone's unfinished thought is not the
    machine's to claim, and that distinction is the one signal the eight-week
    diff depends on.
    """
    brain.require()

    pending = unjournaled(repo, brain)
    if not pending:
        # Nothing new. An earlier run may still have left the journal
        # uncommitted, so try to commit before concluding there is no work.
        commit = brain.commit_paths([JOURNAL_DIR], "journal: commit pending entries")
        return SyncResult(commit=commit)

    append_entries(brain.path, pending)
    dates = sorted({e.local_date for e in pending})
    span = dates[0] if len(dates) == 1 else f"{dates[0]}..{dates[-1]}"
    commit = brain.commit_paths(
        [JOURNAL_DIR],
        f"journal: {len(pending)} {'entry' if len(pending) == 1 else 'entries'}, {span}",
    )

    if recorder is not None:
        for entry in pending:
            recorder.record_event(
                lane="brain",
                kind="file_write",
                label=f"journaled to {entry.local_date}",
                entry_id=entry.entry_id,
            )

    return SyncResult(
        journaled=[e.entry_id for e in pending], commit=commit, dates=dates
    )


def backlog(repo: Repository, brain: BrainRepo) -> int:
    """How many captured entries are not yet in the brain.

    Retrievable without reading the journal by hand, so a brain falling behind
    is visible rather than discovered in week eight.

    Returns -1 when the brain is unavailable. Availability is checked
    explicitly: `journaled_ids` tolerates a missing directory and returns an
    empty set, so without this an absent brain would report every entry as
    merely unjournaled — indistinguishable from a brain that is present and
    behind, which is the confusion this whole capability exists to prevent.
    """
    try:
        brain.require()
        return len(unjournaled(repo, brain))
    except BrainUnavailable:
        return -1
