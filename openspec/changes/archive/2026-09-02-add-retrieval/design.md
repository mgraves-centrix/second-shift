## Context

See `proposal.md` — Why, for the motivation. What follows is only the state
that shapes the approach.

`Embedder` (`providers/base.py`) already exists: `embed(texts, *, policy)`
public, `_do_embed` abstract, the base class recording one `events` row per
call and running `assert_permitted` before `_do_embed` executes. `HashEmbedder`
(`providers/null.py`) is the only implementation, bound unconditionally on
every profile including `cloud` — there is no profile-conditional embedder
binding today, unlike the reasoner, where `_local_reasoner()` already refuses
to bind a placeholder when unconfigured.

No `retrieval/` package exists. No embedding storage exists in the schema.
`privacy-airlock/spec.md` already carries "Context is assembled and filtered
locally," written ahead of anything that implements it. `VllmReasoner` is the
only precedent for a served-model provider client: `urllib`/`json` against an
OpenAI-compatible endpoint, config in `config/models.toml`, no SDK.

This implements ADR 0002 (brute-force cosine, no vector database) rather than
superseding it — nothing here reopens the mechanism ADR 0002 settled, only the
two questions it left to this capability.

> **Corrected 2026-09-02 by [ADR 0011](../../../../docs/decisions/0011-embeddings-are-not-persisted.md).**
> The paragraph above is wrong and is left as written because it is the record of
> what was believed while this shipped. ADR 0002's Decision section says
> "Embeddings are stored as `BLOB`s in SQLite"; this change forbids persisting
> them. That is a supersession, and asserting otherwise here is what kept it from
> being noticed.

## Goals / Non-Goals

**Goals:**
- A real `Embedder` implementation, replacing `HashEmbedder` in every path
  except tests, without touching the interface it implements.
- A `retrieval` package that assembles bounded, ordered, attributable,
  policy-filtered context from `entries` and the brain.
- Retrieval available identically on every profile — the assembly function
  does not know or care which profile it is running under.
- Brain content readable at a pinned commit, reusing `BrainRepo.topic_files_at`
  rather than a second reader.

**Non-Goals:**
- A reranker. Deferred to week 4+ per `docs/MODELS.md`.
- A chunking framework. Topic files today are 1.2–1.8 KB; splitting adds
  complexity the corpus does not yet justify. If a file ever needs splitting,
  split on markdown headings — nothing more elaborate.
- Wiring retrieval into the night pipeline or agents. That is `night-pipeline`
  and `agents`' job; this capability provides the function they call.
- Web research or any external source. That is `research`.
- Persisting anything. See Decisions, below.

## Decisions

**Where the index lives: rebuilt in memory, never persisted.** Full reasoning
and the real corpus measurement are in `proposal.md`. Restated only as a
decision: a `RetrievalIndex` holds one `numpy` array (`float32`, shape
`(n_documents, 2048)`) and a parallel list of document metadata, built once at
process start and rebuildable on demand. Nothing about this decision is
revisited here — measurement already settled it.

Alternatives considered:
- *A new SQLite table.* Rejected — a migration, `is_synthetic` handling and
  backup bloat for a value 100% derivable from `entries` and the brain, at a
  corpus size where derivation costs nothing.
- *A file beside the database.* Rejected — introduces a split-brain failure
  mode (index and database disagreeing after a crash) that in-memory rebuild
  cannot have, because it is always recomputed from the sources of truth.

**How the embedder is reached: a served vLLM endpoint, not an in-process
library.** A new `VllmEmbedder(Embedder)` in `providers/`, mirroring
`VllmReasoner` almost exactly: `_do_embed` posts to the embeddings endpoint,
parses a JSON array of vectors, returns `list[list[float]]`. Config —
endpoint, port, served-model name — lives in a new `[embedder]` table in
`config/models.toml`, read the same way `_local_config()` reads `[local]`
today. Bound on host port **8201**.

Alternatives considered:
- *`sentence-transformers` or raw `transformers`, loaded in-process.* Rejected
  — adds a large, aarch64-uncertain dependency tree (`torch` plus either
  library) to reimplement serving infrastructure vLLM already provides and
  this codebase has already proven stable on this hardware. The embedding
  model (~1.7B) is well within what vLLM serves; there is no capability gap
  forcing a second serving mechanism.
- *Extending the existing reasoner server to also serve embeddings on the same
  port.* Rejected — conflates two provider interfaces behind one endpoint,
  and `config/models.toml`'s own port table already reserves `8200` for the
  reasoner specifically; a shared port makes the capability probe unable to
  distinguish which service failed when one goes down.

**Binding is profile-conditional, mirroring the reasoner, not unconditional
like today's `HashEmbedder`.** The registry refuses to bind `VllmEmbedder`
where `config/models.toml` has no `[embedder]` entry or the endpoint is
unreachable at probe time, the same shape `_local_reasoner()` already uses —
raising a typed `LocalEmbedderNotConfigured` rather than silently falling
back to hash noise. `HashEmbedder` remains bound only in the test fixture
path, never in a running profile.

**A retrieval failure degrades to no context, never blocks a run.** Embedding
or assembly raising is recorded as a failure by the base class (unchanged
behavior) and re-raised; the *caller* — outside this capability's scope — is
expected to catch it and proceed without context, the same posture "no empty
mornings" already takes toward a failed stage. This capability's contract
stops at "assembly either returns bounded context or raises a recorded
failure"; it does not itself decide what a night stage does with that.

**Document granularity: one document per entry, one per topic file, no
splitting.** `entries.raw_text` is embedded whole per entry. `profile.md` and
`style-guide.md` are each embedded whole. Each file under `skills/` (excluding
`README.md`, matching `topic_files_at`'s existing filter) is embedded whole.
At today's and the projected corpus size, no file is large enough to need
splitting; the non-goal above names the fallback if that ever changes.

**Source identifiers are stable, human-readable strings**, not surrogate ids:
`entry:<entries.id>` for a captured idea, `brain:profile`,
`brain:style-guide`, `brain:skill:<name>` for topic files. This is what each
assembled piece's `source` field carries, and it is what a future debugging
session reads without a join.

**Vector dtype is `float32`.** JSON-transported embedding responses carry no
dtype information; `float32` is the standard choice and is what the proposal's
byte-count math already assumes. `float64` would double storage for no
measured benefit at this corpus size.

## Risks / Trade-offs

- **In-memory rebuild cost grows with corpus size** → Mitigated by the
  measurement in `proposal.md`: 48 KB today, under 5 MB at ten times today's
  size. ADR 0002 already names the escape hatch — revisit when retrieval
  demonstrably falls over, not before.
- **A second co-resident server (embedder, alongside the reasoner) has an
  unmeasured memory footprint** → Spike B measured the reasoner alone (43 of
  121 GiB at `--gpu-memory-utilization 0.30`, 77 free) and left the embedder's
  footprint as explicitly open. This change's Phase 5 verification measures
  resident memory with both servers running, closing that question rather
  than assuming headroom is sufficient.
- **Narrowing the embedder binding could surface a caller that silently
  depended on `HashEmbedder` always being available** → The same narrowing
  already happened once, for the reasoner, in `local-inference`, without
  incident. Any caller that breaks was relying on unspecified behavior.
- **`HashEmbedder`'s "deterministic" docstring is not true across process
  restarts** — found during this proposal's research: it hashes with
  builtin `hash()`, which is salted per-process by default. Not a production
  risk once `HashEmbedder` is test-only, but a test asserting cross-process
  stability against it would be asserting something false. Flagged here so
  `tasks.md` does not write that test.

## Migration Plan

No schema migration ships with this capability. Deployment adds one new
systemd unit (`second-shift-embedder.service`, mirroring the existing
reasoner unit) and one new config block. Rollback is stopping that unit and
reverting the registry binding commit — retrieval becomes unavailable, the
same shape a degraded `local-only` capability already takes, and nothing
downstream that degrades to no-context on failure needs to change.
