# 0011 — Embeddings are derived at startup, not stored

**Status:** accepted · **Date:** 2026-09-02
**Supersedes the storage clause of [0002](0002-no-vector-database.md).** The rest
of 0002 stands unchanged.

## Context

ADR 0002 settled two things in one paragraph, and only one of them was the
question it was called to answer:

> Embeddings are stored as `BLOB`s in SQLite. Search is exact brute-force cosine
> over an in-memory numpy array, behind the `Embedder` and retrieval interfaces.

The sentence that mattered on 27 Aug was the second — *no LanceDB, no
`sqlite-vec`, no native extension of any kind*, decided on aarch64 wheel risk and
on a corpus small enough that exact search is instant. The first sentence rode
along. Nothing measured it, no alternative was written down against it, and it
was never the subject of the ADR's title.

On 2 Sep the `retrieval` capability shipped a requirement that contradicts it
outright:

> No persisted store of vectors SHALL exist that could diverge from those sources
> after a crash or an interrupted write.
> — `openspec/specs/retrieval/spec.md`

Both documents were accepted. Both are in force. A repository cannot hold an
accepted ADR and an accepted spec that say opposite things about the same bytes,
and until this ADR the contradiction was not merely unresolved — it was asserted
away. `2026-09-02-add-retrieval`'s `design.md` says:

> This implements ADR 0002 (brute-force cosine, no vector database) rather than
> superseding it — nothing here reopens the mechanism ADR 0002 settled, only the
> two questions it left to this capability.

and its `proposal.md` says ADR 0002 "settled the search mechanism but not this."
Both are false. ADR 0002 settled storage in as many words, in its Decision
section, and the capability overturned it. Writing "rather than superseding it"
into a design document does not make a supersession not have happened; it makes
it unfindable. That is the defect this ADR exists to correct, and it is worse
than the disagreement it was covering — a reader who trusted `design.md` would
have concluded there was nothing to reconcile.

## Decision

**Embeddings are never persisted.** The index is one `float32` numpy array of
shape `(n_documents, 2048)` plus parallel metadata, built at process start from
`entries` and the brain, and rebuildable on demand. No table, no file, no cache
directory, no column.

ADR 0002's other holdings are untouched and remain accepted:

- Search is exact brute-force cosine over an in-memory numpy array.
- No LanceDB, no `sqlite-vec`, no native extension of any kind.
- Swapping in a real index later is a one-module change behind the interface.
- Revisit only when retrieval demonstrably falls over, not on principle.

## Rationale

**A vector is derived, and this repository already has a rule for derived
things.** `docs/DATA_MODEL.md` states it as a convention — *counters are views,
never stored columns*. An embedding is a pure function of `raw_text` and brain
content at a commit. Storing it makes a second copy of something already stored,
and the two copies can disagree.

**Persisting it buys a saving that does not exist at this scale.** 2048
dimensions at `float32` is 8 KB a vector: 48 KB against today's corpus, under
5 MB at ten times the week-eight projection of ~600 entries. A migration,
append-only semantics, `is_synthetic` handling and permanent backup bloat is a
large price for skipping a rebuild that costs a few seconds of embedding calls
against a model that is already resident.

**The failure mode is the decisive argument, not the disk.** A stored index and
its sources can diverge after a crash or an interrupted write, and a diverged
index is silent — retrieval returns plausible, subtly stale context and nothing
raises. An index rebuilt from the sources of truth cannot have that failure,
because there is nothing durable to be stale. This is the same reason the brain
is plaintext under git rather than a second database: one place to be wrong.

**It also strengthens principle 1.** Deleting the index loses nothing, by
construction. That is a property worth having in a system whose whole claim is
that the brain is the artifact.

## Consequences

- `docs/DATA_MODEL.md`'s "Vectors are `BLOB`s in SQLite" paragraph was wrong from
  the day retrieval shipped. Corrected in the same commit as this ADR.
- Startup pays an embedding pass over the corpus. At ~600 documents against a
  resident model this is seconds, and it is the only cost this decision adds.
- The escape hatch is unchanged and is ADR 0002's own: revisit when retrieval
  demonstrably falls over. A corpus two orders of magnitude past the projection,
  or a startup budget that cannot absorb the rebuild, is what "falls over" would
  look like. Neither is close.
- **A process finding, recorded because it is the more useful half of this ADR.**
  `openspec/config.yaml`'s archive gate already says *"if the change established
  or altered an architectural decision, confirm a corresponding ADR exists in
  `docs/decisions/` before archiving."* `2026-09-02-add-retrieval` altered ADR
  0002 and was archived with no ADR behind it. The gate did not fail on a
  technicality: it was answered from the change's own account of itself — a
  `design.md` sentence saying no decision was altered — instead of from the
  decision's text. **The check has to read the ADR.** A change document is not
  evidence about the document it contradicts.
