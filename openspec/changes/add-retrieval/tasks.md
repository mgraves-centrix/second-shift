## 1. Foundation

- [ ] 1.1 Add `numpy` to `apps/api/pyproject.toml` and verify
  `python -c "import numpy"` succeeds inside the venv.
- [ ] 1.2 Add an `[embedder]` table to `config/models.toml` — host, port
  `8201`, served-model name `nvidia/llama-nemotron-embed-vl-1b-v2`, timeout —
  matching `[local]`'s existing shape. Add the port to the file's own port
  table comment. Verify by reading the file back and confirming `tomllib`
  parses it.
- [ ] 1.3 Add `_embedder_config()` to `config.py`, mirroring `_local_config()`,
  and a typed settings accessor mirroring `local_reasoner_settings()`. Verify
  with a unit test that an absent `[embedder]` table produces the documented
  "not configured" result rather than a `KeyError`.

## 2. The embedder provider

- [ ] 2.1 Implement `VllmEmbedder(Embedder)` in `providers/vllm_embedder.py`
  (or the equivalent module inside `providers/`) — `_do_embed` posts to the
  configured endpoint, parses the response into `list[list[float]]`. No
  telemetry code in this class; the base class already owns it. Verify with
  `grep -c "record_" providers/vllm_embedder.py` returning `0`, mirroring
  `test_null_providers_contain_no_telemetry_code`'s existing pattern.
- [ ] 2.2 Write `LocalEmbedderNotConfigured`, raised when `[embedder]` is
  absent or the endpoint fails the capability probe — mirroring
  `LocalReasonerNotConfigured` exactly. Verify with a test asserting the
  registry raises it rather than falling back to `HashEmbedder` on an
  unconfigured profile.
- [ ] 2.3 Narrow the registry: bind `VllmEmbedder` where configured,
  `HashEmbedder` only inside the test fixture path — never in a bound profile.
  Verify every existing test in `test_providers.py` and
  `test_registry.py` (or wherever profile binding is tested today) still
  passes, since this changes production binding behavior the same way
  `local-inference` already changed the reasoner's.
- [ ] 2.4 Write `deploy/spark/second-shift-embedder.service`, mirroring
  `second-shift-reasoner.service` — restart policy, port `8201`. Verify by
  diffing the two unit files and confirming only the expected fields differ
  (image, port, served-model name).

## 3. The retrieval package

- [ ] 3.1 Create `apps/api/secondshift/retrieval/` with a `ContextPiece`
  dataclass (`text`, `score`, `source`, `policy`) and a `RetrievalIndex`
  class holding one `numpy.float32` array of shape `(n, 2048)` plus parallel
  document metadata. Verify with a unit test constructing an index from a
  handful of known vectors and asserting the array's shape and dtype.
- [ ] 3.2 Implement `RetrievalIndex.rebuild()` — reads every `entries` row via
  `Repository`, every topic file via `BrainRepo.topic_files()` (or
  `topic_files_at(sha)` when a commit is pinned), embeds each as one document
  per the design's granularity decision, and populates the array. Source
  identifiers follow the `entry:<id>` / `brain:profile` / `brain:style-guide`
  / `brain:skill:<name>` scheme from `design.md`. Verify with a test seeding
  known entries and brain content, rebuilding, and asserting the expected
  source identifiers appear.
- [ ] 3.3 Implement `RetrievalIndex.search(query_vector, k)` — exact cosine
  similarity against every row, returning the top `k` `ContextPiece`s in
  descending score order with a stable tie-break. Verify with a test
  asserting an obviously-matching document ranks above an obviously-unrelated
  one, and that a tie between two equal-score documents resolves the same way
  on repeated runs.
- [ ] 3.4 Implement `assemble_context(query, *, policy, max_pieces)` — embeds
  the query, searches, filters by policy **before** returning, and bounds the
  result to `max_pieces`. Verify with the airlock test below.
- [ ] 3.5 Handle an embedding or search failure by letting it propagate as a
  recorded failure (per `design.md`'s "degrades to no context" decision) —
  do not swallow it inside `retrieval/`. Verify with a test that a raised
  `_do_embed` exception surfaces to `assemble_context`'s caller rather than
  being caught and hidden.

## 4. Verification that can fail

- [ ] 4.1 **The airlock test.** Assemble context for a prompt destined for a
  remote provider, where the corpus includes a `local-only` entry that is the
  best textual match. Assert the assembled structure contains no substring of
  that entry's raw text. Then remove the policy filter and confirm the test
  goes red — this proves the test can fail, not only that it currently
  passes.
- [ ] 4.2 Assert retrieval on the `cloud` profile constructs no remote
  embedding provider — inspect the registry's bound instance, not merely
  that no network call happened, mirroring `RETRIEVAL.md`'s own instruction
  that this must be checked at construction, not only at call time.
- [ ] 4.3 Assert rebuilding the index after deletion returns identical search
  results to before deletion, over a fixed corpus and a fixed query.
- [ ] 4.4 Assert reading the brain at two different pinned commits returns
  each commit's actual content, using `BrainRepo.topic_files_at`.

## 5. Spark verification

- [ ] 5.1 Deploy the embedder unit to the Spark alongside the running
  reasoner. Embed the real corpus (today: 4 entries, `profile.md`,
  `style-guide.md`) with the real model and report wall-clock rebuild time.
- [ ] 5.2 Report resident memory with **both** servers running — this closes
  Spike B's open co-residency question, which measured the reasoner alone.
- [ ] 5.3 Run the full suite on the Spark
  (`COPYFILE_DISABLE=1` transfer, `python -m venv`, pinned constraints,
  **never `uv run`**) and confirm it passes on 3.12/aarch64, not only on the
  local dev interpreter.
- [ ] 5.4 Clean up whatever was created on the Spark for this verification
  and confirm capture still works (`/health`, `/capabilities`, brain
  `--status`) before ending the session.
