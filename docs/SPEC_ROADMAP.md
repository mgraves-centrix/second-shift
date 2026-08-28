# Spec Roadmap

What gets specified next, in the order the work unblocks. One OpenSpec change
per capability unless noted.

Shipped: `persistence`, `telemetry`, `compute-profiles`, `privacy-airlock`
(archived as `2026-08-27-add-foundations`).

Each entry lists what is **already decided** — so the proposal has material to
draw on rather than re-deriving it — and what is **still open**, which becomes
`[NEEDS CLARIFICATION]` markers rather than assumptions.

---

## Blocking issue to resolve first

**The day-3 eval baseline has no judge.** `docs/WEEK_ONE.md` puts the week-1
eval baseline on day 3, but the local reasoner does not exist until day 4 and
Token Factory is not verified until day 5. On day 3 there is no model to
generate outputs and none to score them.

The week-1-versus-week-8 comparison is the submission's centerpiece, so this
cannot silently slip. Two workable shapes:

- **Split the baseline.** Day 3 records the fixed prompts, the rubric SHA and
  the brain SHA — the things that must be captured *at that moment* and cannot
  be reconstructed later. Scoring runs on day 5 against the recorded brain
  state. The `eval_runs` schema already separates `brain_sha` from
  `judge_model`, so this needs no schema change.
- **Move the baseline to day 5.** Simpler, but the brain has then absorbed two
  more days of dogfooding, so "week 1" measures a slightly later brain.

The first preserves the measurement; the second is less work. This is a real
decision, not a detail — it belongs in the `evals` proposal as a blocking
question.

---

## Week one

### 1. `capture` — day 2, critical path

Entries from the PWA to a logged row. Everything downstream waits on it, and
day-3 dogfooding starts the memory clock that cannot be restarted.

**Decided:** entry schema and timezone fields; text-first with voice layered
later; policy selected at capture; unavailable policies shown disabled with
their specific reason (never hidden); offline-tolerant queue.

**Open:** whether latitude/longitude are captured per entry or configured once
(the celestial layer needs them, but a per-capture geolocation prompt adds
friction to the one interaction that must stay frictionless); how a replayed
offline queue avoids duplicate entries; whether titles are derived or entered.

### 2. `brain` — day 3

The plaintext memory: a sibling git repository the orchestrator reads and
commits to.

**Decided:** ADR 0001 — separate repository, not a subdirectory or submodule;
human-readable markdown; `runs.brain_sha` pins state per run.

**Open:** file layout — per-day files, per-entry files, or by topic; commit
granularity (per entry, per stage, per night); what the brain contains on day
one before any night has run.

### 3. `evals` — day 3, subject to the blocking issue above

The measurement spine. Run 1 must exist early or the week-8 comparison has no
left-hand side.

**Decided:** schema exists; judge model and rubric SHA are pinned per run;
repeated sampling gives variance rather than a point estimate.

**Open:** the five held-out prompts; the rubric itself; and the sequencing
question above.

### 4. `local-inference` — day 4

vLLM serving Nemotron 3.5 Lightning, implementing `Reasoner` against the
existing interface.

**Decided:** model bindings in ADR 0006 and `docs/MODELS.md`; NVFP4 with DSpark
speculative decoding; the base class already owns telemetry, so this
implements `_do_complete` only.

**Open:** quantization and speculative-decoding configuration under sustained
load; whether reasoner, ASR and embedder stay co-resident on 128GB.

### 5. `nebius-executor` — day 5

**Carries every obligation deferred out of day 1. These are written down here
because a deferred obligation with no home is a dropped one.**

- The authenticated telemetry ingest endpoint. The recorder-side contract
  exists and is tested; the transport does not.
- **Reachable from Nebius without exposing the machine that holds the brain to
  the public internet.** Joining the job to the tailnet is the intended route;
  a public endpoint widens the attack surface on the always-on machine and
  needs an explicit decision before it is built.
- Ingest must serialize through the orchestrator's writer, never a second
  connection.
- **Real per-token rates replacing the placeholders in `config/pricing.toml`.**
  Every cloud call fails loudly until this lands — deliberate, but it means the
  first Token Factory call is blocked on it.
- Resolution of the judge deployment target.

**Decided:** ADR 0004 — build stage fans out to parallel variants, one job each;
`Executor.dispatch` carries the telemetry descriptor; `JobResult` never carries
telemetry.

**Open:** the ingest transport and its authentication; retry and idempotency
when a job reports telemetry twice.

### 6. `synthetic-seed` — day 6

The night generator. Unblocks all frontend work and seeds the judge instance.

**Decided:** every row carries `is_synthetic = 1`; rollup views already exclude
it; a full night is roughly six hours and 400+ events across lanes.

**Open:** how realistic the generated content must be to be worth screenshotting.

### 7. `night-timeline` — day 7

The playback contract behind the scrubber. Built once, used three times.

**Decided:** `events` carries pre-rendered scalar columns so rendering never
parses JSON; `duration_ms` non-null renders as a bar, null as a tick; the
invocation tree renders as lanes over time.

**Open:** the query contract for a time window at 20x; how deep the invocation
tree renders before it needs collapsing.

---

## Week two and beyond

| Capability | Covers |
|---|---|
| `night-pipeline` | The checkpointed stage machine. "No empty mornings" as executable behavior rather than a schema affordance. |
| `morning-interview` | Briefing from the log delta, then queued questions. The product. |
| `retrieval` | Local embedding, assembly, policy filtering before egress. Brute-force cosine per ADR 0002. |
| `research` | Tavily search, extract, crawl. Redaction before any query leaves; credit accounting. |
| `artifacts` | Briefs, mockups, builds. Variant grouping and critic ranking; outcome capture. |
| `judge-mode` | The demo instance: cloud profile, synthetic persona, labeled in-UI, "run the night". |

---

## Ordering rule

`capture` before everything, because day-3 dogfooding starts a clock that cannot
be restarted. `nebius-executor` before any cloud reasoning, because the pricing
placeholders make every cloud call fail until it lands. `synthetic-seed` before
`night-timeline`, because a scrubber cannot be built against three events.
