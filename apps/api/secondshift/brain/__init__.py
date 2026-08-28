"""The plaintext memory.

Markdown in a sibling git repository, per ADR 0001 and the first constitution
principle. Nothing here abstracts over git or over the filesystem: the brain's
whole value is being ordinary enough to open in a text editor, and an
abstraction over that is the opaque store the principle forbids wearing a
different coat.
"""

from .journal import JournalEntry, journal_path, journaled_ids, render_entries
from .repo import BrainRepo, BrainUnavailable
from .sync import SyncResult, sync

__all__ = [
    "BrainRepo",
    "BrainUnavailable",
    "JournalEntry",
    "SyncResult",
    "journal_path",
    "journaled_ids",
    "render_entries",
    "sync",
]
