"""Local retrieval: what the system knows, ranked against what it was asked.

The index is derived and disposable. `entries` and the brain are the sources of
truth; this package holds vectors over them in memory and rebuilds from scratch
rather than persisting anything, so deleting it loses nothing (ADR 0002, and
principle 1 — the index is an index, never the other way round).

Assembly is where the Privacy Airlock stops being policy and becomes mechanism.
`assemble_context` filters by policy *before* it returns, so a `local-only`
document is never inside a structure that a caller could hand to a remote
provider.
"""

from .index import ContextPiece, Document, RetrievalIndex, assemble_context

__all__ = ["ContextPiece", "Document", "RetrievalIndex", "assemble_context"]
