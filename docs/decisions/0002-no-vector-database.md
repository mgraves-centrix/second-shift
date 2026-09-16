# 0002 — No vector database

**Status:** accepted · **Date:** 2026-08-27
**Superseded in part by [0011](0011-embeddings-are-not-persisted.md)** — embeddings
are not stored. Everything else here stands. The sentence is left as written: it
was accepted for six days and a capability shipped against it.

## Context

The original stack specified LanceDB alongside SQLite and markdown. Two facts
changed the calculus:

1. Projected scale is roughly 600 entries by week eight — five to ten captures a
   day for nine weeks.
2. The product must run for people who do not own a DGX Spark, which means the
   dependency set has to install identically on aarch64, x86, and inside the
   judge container.

## Decision

Embeddings are stored as `BLOB`s in SQLite. Search is exact brute-force cosine
over an in-memory numpy array, behind the `Embedder` and retrieval interfaces.

No LanceDB. No `sqlite-vec`. No native extension of any kind.

## Consequences

- Search is *exact*, not approximate, and instant at this scale.
- One fewer store to keep consistent with SQLite and markdown.
- Zero aarch64 wheel risk on a platform where every wheel is a coin flip — the
  brief already lists four dependency landmines; this avoids volunteering for a
  fifth.
- Swapping in a real index later is a one-module change behind the interface.
- Revisit only when retrieval demonstrably falls over, not on principle.
