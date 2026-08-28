"""The journal: raw captured history, one file per local date.

Written for a human first. Someone should be able to open a day and read what
they thought, in order, without tooling — a memory nobody can read by hand is
the opaque store the constitution forbids, whatever format it is in.

The entry identifier appears in each heading. That is what lets journaled-ness
be *derived* from the journal rather than stored in a column: the journal is the
only thing that actually knows what is in the journal, and a flag beside it
could disagree.
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass
from pathlib import Path

from .repo import JOURNAL_DIR

#: Matches the identifier in an entry heading. Kept narrow — a ULID is 26
#: Crockford base32 characters, so this cannot match prose.
_ENTRY_ID = re.compile(r"^##\s+\d{2}:\d{2}:\d{2}\s+·\s+[a-z-]+\s+·\s+([0-9A-HJKMNP-TV-Z]{26})\s*$", re.M)


@dataclass(frozen=True, slots=True)
class JournalEntry:
    """One captured idea, as the journal records it."""

    entry_id: str
    created_at_ms: int
    tz_offset_min: int
    captured_tz: str
    policy: str
    text: str
    title: str | None = None

    @property
    def local(self) -> dt.datetime:
        """Wall-clock time where the entry was captured.

        Derived from the offset recorded at the capture instant rather than from
        the zone name, so a daylight-saving transition resolves to the moment
        that actually happened.
        """
        moment = dt.datetime.fromtimestamp(self.created_at_ms / 1000, tz=dt.UTC)
        return moment + dt.timedelta(minutes=self.tz_offset_min)

    @property
    def local_date(self) -> str:
        return self.local.strftime("%Y-%m-%d")


def journal_path(brain: Path, local_date: str) -> Path:
    return brain / JOURNAL_DIR / f"{local_date}.md"


def journaled_ids(brain: Path) -> set[str]:
    """Identifiers already present in the journal.

    Reads the files. There is deliberately no stored flag to consult, and so
    nothing that can drift from what is actually written.
    """
    directory = brain / JOURNAL_DIR
    if not directory.is_dir():
        return set()
    found: set[str] = set()
    for path in directory.glob("*.md"):
        found.update(_ENTRY_ID.findall(path.read_text()))
    return found


def render_entries(entries: list[JournalEntry]) -> str:
    """Render entries for one date, in capture order."""
    ordered = sorted(entries, key=lambda e: (e.created_at_ms, e.entry_id))
    blocks = []
    for entry in ordered:
        heading = (
            f"## {entry.local.strftime('%H:%M:%S')} · {entry.policy} · {entry.entry_id}"
        )
        body = entry.text.strip()
        meta = f"*{entry.captured_tz}*"
        blocks.append(f"{heading}\n\n{meta}\n\n{body}\n")
    return "\n".join(blocks)


def append_entries(brain: Path, entries: list[JournalEntry]) -> list[Path]:
    """Append entries to their own dates' files. Returns the files touched.

    An entry files under the date it was *captured*, not the date it arrived —
    an idea captured at 23:50 and drained the next morning belongs to the night
    it was had.
    """
    by_date: dict[str, list[JournalEntry]] = {}
    for entry in entries:
        by_date.setdefault(entry.local_date, []).append(entry)

    touched: list[Path] = []
    for local_date, group in sorted(by_date.items()):
        path = journal_path(brain, local_date)
        path.parent.mkdir(parents=True, exist_ok=True)
        existing = path.read_text() if path.is_file() else f"# {local_date}\n"
        if not existing.endswith("\n"):
            existing += "\n"
        path.write_text(existing.rstrip("\n") + "\n\n" + render_entries(group))
        touched.append(path)
    return touched
