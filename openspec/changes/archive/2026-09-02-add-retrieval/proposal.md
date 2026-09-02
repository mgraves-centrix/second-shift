## Why

Nothing reads the brain. `HashEmbedder` returns deterministic noise from
`hash()` on the raw text, bound on every profile including `cloud`, and
`privacy-airlock/spec.md` already carries a requirement — "Context is assembled
and filtered locally" — that nothing implements yet. The eight-week claim is
that the system gets better at being you; without retrieval, the brain is a
directory nobody reads, and a night's `agent_invocations` cannot pull anything
real into a prompt.

`ADR 0002` settled the mechanism — brute-force cosine over an in-memory numpy
array, no vector database — but not where the vectors live between rebuilds,
and not how the embedding model itself is reached. Both are answered here from
measurement and precedent rather than left open.

## What Changes

**An `Embedder` implementation over vLLM's OpenAI-compatible embeddings
endpoint**, mirroring `VllmReasoner` exactly: `urllib`/`json`, no SDK, endpoint
and served-model name in `config/models.toml`. vLLM already serves embedding
models through the same server type the reasoner uses, so this reuses proven
aarch64 infrastructure rather than adding `torch`/`transformers` as a second,
redundant dependency chain — a real risk on this platform, where "every wheel
is a coin flip" is not a figure of speech (`CLAUDE.md`). Binds
`nvidia/llama-nemotron-embed-vl-1b-v2` (ADR 0006, `docs/MODELS.md`) on host
port **8201** — the next free slot after `8200` (reasoner) in the table
`config/models.toml` already documents, keeping `8000` free as that table
requires.

**A `retrieval` package**: assembly of bounded, ordered, policy-filtered
context from the brain's topic files and captured entries, with the score,
source and policy of each included piece visible to the caller. Runs locally
on every profile, `cloud` included — there is no configuration path that
routes it to a hosted embedding endpoint, because `privacy-airlock/spec.md`
forbids one and a switch that could be flipped is a switch that will be.

**No new table, no new file.** The index is rebuilt in memory from `entries`
and `BrainRepo` at startup and on demand. Measured against the real corpus
today — 4 entries (218 bytes of `raw_text` combined) plus `profile.md` (1816
bytes) and `style-guide.md` (1222 bytes); `skills/` holds only a `README.md`,
which `topic_files_at` already excludes, so it currently contributes nothing —
that is 6 documents, `6 × 2048 × 4` bytes of `float32` vectors: 48 KB. At
ADR 0002's own projected week-8 scale, roughly 600 entries, the same arithmetic
is under 5 MB. Full reasoning in "Decisions taken without a marker" below.

**`numpy` becomes a direct dependency.** ADR 0002 specifies "an in-memory numpy
array" and it is not currently in `apps/api/pyproject.toml` — confirmed absent
from both the manifest and the installed venv. Adding it is not a new
architectural choice; it is finishing the one already made.

Not in this change: research, a reranker, a chunking framework beyond
splitting on headings. Each is its own capability or explicitly deferred by
`docs/MODELS.md`.

## Capabilities

### New Capabilities
- `retrieval`: local embedding of the brain and captured entries, brute-force
  cosine search, and policy-filtered context assembly behind the `Embedder`
  and a new retrieval interface.

### Modified Capabilities
(none — `privacy-airlock/spec.md`'s "Context is assembled and filtered
locally" requirement does not change wording; this change is what makes it
true for the first time. See Impact.)

## Impact

**New code:** `apps/api/secondshift/retrieval/` (assembly, cosine search);
`apps/api/secondshift/providers/vllm_embedder.py` or equivalent within
`providers/` (the served-model client); a new `[embedder]` table in
`config/models.toml`; `deploy/spark/second-shift-embedder.service` mirroring
the existing reasoner unit.

**Changed:** `apps/api/pyproject.toml` (adds `numpy`); the registry binds the
real embedder on profiles where the server is configured, mirroring
`_local_reasoner()`'s refusal to silently bind a placeholder when unconfigured
— today `HashEmbedder` is bound unconditionally everywhere, which this change
narrows the same way `local-inference` already narrowed the reasoner binding.

**Not changed:** the schema. No migration ships with this capability — see
above.

**Satisfies without editing:** `privacy-airlock/spec.md`'s existing retrieval
requirement, and closes the gap `docs/SPEC_ROADMAP.md` names under
`retrieval`'s entry.

## Constitution Compliance

| Principle | Status | Note |
|---|---|---|
| 1. Brain plaintext under git | **Constrains** | The brain is the source of truth; the in-memory index is exactly that — an index, never a second store. Deleting it and restarting loses nothing, by construction: there is nothing durable to delete. |
| 2. Privacy Airlock | **Constrains, and is the sharpest risk here** | Retrieval runs locally on every profile, `cloud` included; `embed()` already calls `assert_permitted` before `_do_embed` runs. Assembly returns only bounded, filtered context — a `local-only` entry's raw text must never appear in a structure eligible for egress. This is the capability that makes the existing privacy-airlock requirement real rather than aspirational. |
| 3. No empty mornings | Not applicable | Retrieval is not a night stage with commit semantics; a caller that cannot get context should degrade to none rather than block, which is a design note here, not a constitution obligation. |
| 4. Text-first | Not applicable | No voice surface. |
| 5. One codebase, two deployments | **Implements** | The embedder is a served vLLM endpoint reached only through the `Embedder` interface, the same shape as the reasoner. No provider SDK or model identifier appears outside `providers/` — `TestNoProviderLeakage`'s source scan already enforces this and will fail the build otherwise. |
| 6. Scope boundary | Compliant | Nothing in `NOT_BUILDING.md`. No reranker, no chunking framework, no research — each deferred to its own capability. |
| 7. Telemetry from line one | **Implements** | `Embedder`'s base class already records an `events` row per call; this change does not bypass it. No new table means no new `is_synthetic` surface to guard. |

No violations.

## Decisions taken without a marker

**Where the index lives: in memory, rebuilt at startup and on demand — not a
table, not a file.** `ADR 0002` settled the search mechanism but not this.
Measured against the real corpus rather than assumed:

- A table means a migration, append-only semantics for a value that is 100%
  derivable from data already stored, and vectors bloating every backup.
  `docs/DATA_MODEL.md`'s own convention — "counters are views, never stored
  columns" — applies to the same category of thing here: a vector is a derived
  artifact of `raw_text` and brain content, not an independent fact.
- A file beside the database means the index and the database can disagree
  after a crash. In-memory rebuild has no such failure mode, because it is
  always recomputed from the sources of truth.
- The real numbers make the cost of either alternative hard to justify: 48 KB
  today, under 5 MB at ten times today's corpus. `ADR 0002`'s own text —
  "revisit only when retrieval demonstrably falls over, not on principle" —
  is the standing instruction if that ever changes.

The one number this reasoning does not include is real embedding latency on
the Spark, because nothing is deployed to measure it against yet — no cached
model, no inference library in the venv, confirmed by direct check. Standing
that up is this capability's own implementation, not a proposal precondition.
It is verified in Phase 5, per the requirement below, before this ships.

**How the embedder is reached: vLLM, not a second dependency chain.** The
alternative — loading the model in-process via `transformers` or
`sentence-transformers` — would add a new, large, aarch64-uncertain dependency
tree to do what a server already proven on this hardware does. vLLM supports
embedding models through the same OpenAI-compatible shape `VllmReasoner`
already speaks. Reusing it costs one new systemd unit and one new port; the
alternative costs an unproven dependency install on the one platform where
that has already caused problems.
