# Spec Roadmap

What gets specified next, in the order the work unblocks. One OpenSpec change
per capability unless noted.

Shipped, in the order they landed: `persistence`, `telemetry`,
`compute-profiles`, `privacy-airlock` (`2026-08-27-add-foundations`, and
`2026-08-27-fix-probe-model-identity`), then `capture`, `brain`, `evals`,
`synthetic-seed` and `local-inference`. Nine canonical capabilities across eight
archived changes, all under `openspec/changes/archive/`.

Each entry lists what is **already decided** — so the proposal has material to
draw on rather than re-deriving it — and what is **still open**, which becomes
`[NEEDS CLARIFICATION]` markers rather than assumptions. Headings are marked
shipped as they land; an entry still carrying an **Open** line is one nobody has
answered yet.

---

## Resolved 2026-08-27

- **Eval baseline is split.** Day 3 records prompts, `rubric_sha` and
  `brain_sha`; scoring runs day 5 once a judge exists. Detail below.
- **Geolocation: configured home, per-entry override.** Home lat/long in config
  keeps capture frictionless; an explicit override covers capture while
  traveling. No browser geolocation prompt.
- **Brain layout: stable topic files plus a dated journal.** Detail below.
- **Offline replay dedup** uses the client-generated ULID as an idempotency
  key. The client already needs an id to queue an entry offline.
- **Titles are derived, not entered.** Typing a title is friction on the one
  interaction that must stay frictionless.
- **Repository is public** as of 2026-08-27, Apache 2.0, history audited first.

---

## The eval sequencing problem, and its resolution

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

**Resolved: split the baseline.**

Day 3 records only what cannot be reconstructed later — the five fixed prompts,
the `rubric_sha`, and the `brain_sha` of a two-day-old brain. No model is
required for that. Day 5 generates and scores against that recorded brain
state, once Token Factory is verified.

`eval_runs` already separates `brain_sha` from `judge_model`, so this needs no
schema change. What it does need is for the day-5 scoring run to be pinned to
the day-3 `brain_sha` rather than to whatever HEAD is by then — that is the
whole point, and it is the one thing that can silently go wrong.

---

## Week one

### 1. `capture` — shipped 28 Aug

Entries from the PWA to a logged row. Everything downstream waits on it, and
day-3 dogfooding starts the memory clock that cannot be restarted.

**Decided:** entry schema and timezone fields; text-first with voice layered
later; policy selected at capture; unavailable policies shown disabled with
their specific reason (never hidden); offline-tolerant queue.

**Also decided:** home lat/long in config with a per-entry override; offline
replay deduplicated on the client-generated ULID; titles derived rather than
entered.

**Resolved and shipped.** The surface shows a persistent *count* of entries
captured and not yet acknowledged, and nothing per-item. A count is enough to
stop a re-tap; a list is not, because a per-item surface is what a retry, edit
or delete control attaches to, and `NOT_BUILDING.md` excludes task management.
The count clears on drain without user action.

### 2. `brain` — shipped 28 Aug

The plaintext memory: a sibling git repository the orchestrator reads and
commits to.

**Decided:** ADR 0001 — separate repository, not a subdirectory or submodule;
human-readable markdown; `runs.brain_sha` pins state per run.

**Also decided:** stable topic files — `profile.md`, `style-guide.md`,
`skills/*.md` — rewritten in place as the system learns, alongside a dated
append-only journal for raw history. The eight-week diff is read off the topic
files: a diff of an append-only log is just more stuff, while a diff of an
edited belief file *is* the learning claim, visible.

**Resolved and shipped.** One commit per sync batch. Sync stages `journal/`
rather than the tree, so a hand-edited topic file is never swept into an
automated commit. Local-only, no remote, mirrored to a NAS.

**The brain lives on the always-on machine**, beside the database the
orchestrator writes — not on the development laptop. ADR 0001 said "sibling
repository" and left the machine implicit; sync has no brain to write to if the
two are on different hosts, which only became obvious when sync first ran. Edit
topic files there, or clone and push back.

**Still open:** what the topic files should contain, which is a question for
their subject rather than for the code. The seeded profile is explicitly a
sketch asking to be corrected.

### 3. `evals` — shipped 28 Aug

The measurement spine. Run 1 must exist early or the week-8 comparison has no
left-hand side.

**Decided:** schema exists; judge model and rubric SHA are pinned per run;
repeated sampling gives variance rather than a point estimate.

**Shipped: the machinery, deliberately without the content.** The runner, the
scoring path, repeated sampling, and the `eval_runs` / `eval_results` writes,
with the prompts left as data so choosing them is data entry rather than a code
change. Rubric v1 is committed at `config/evals/rubric.md` and hashed by content
rather than by the commit that touched it. The sequencing question above is
resolved.

**Which five are held out is database state, not repository state.** The ten
candidates live in `config/evals/candidates.md`; the selection is
`eval_prompts.active`, set by `python -m secondshift.evals activate <slug>` and
read back by `python -m secondshift.evals status`. It lives beside the database
on the always-on machine, so **a clone cannot show it** — do not read an
unmarked `candidates.md` as an unmade decision.

**The week-1 baseline exists.** Confirmed on the always-on machine, 2 Sep: five
prompts active, one `eval_runs` row awaiting scoring. The day-3 gate is met and
the clock that could not be restarted was started on time.

**Still open:** scoring, which needs a judge and a generating provider — that is
`local-inference` and `nebius-executor`, not this capability.

**Blocking scoring — the rubric on the machine is not the rubric in this
repository.** `status` there reports `4a7c2e91b3d0`. `config/evals/rubric.md` has
exactly one version in the whole history, at `a4fb4da`, and it hashes to
`b4decd6fe774`. No committed version has ever hashed to what the machine reports,
so this is not a checkout sitting behind — it is a copy of the file that git has
never seen.

Two values are involved and only one is known. `status` hashes the file **on disk
at the moment it runs**; the pinned value is `eval_runs.rubric_sha` on the
baseline row, and nothing has printed it yet.

- If the baseline pinned `4a7c2e91b3d0`, week 1 is pinned to a rubric absent from
  a public repository whose entire argument is that the measurement is
  reproducible from it.
- If it pinned `b4decd6fe774`, the baseline is sound and the file drifted
  afterward — still fatal at scoring time, because `score` reads the file on disk
  and would grade week 1 against a rubric the baseline never used.

Either way it is resolved before a judge runs, not after.

**The instrument now exists** — `2026-09-02-reconcile-rubric-pinning`. `status`
reports every recorded run's pinned `rubric_sha` and `brain_sha` beside the hash
of the file on disk, says so plainly when they disagree, and exits non-zero. On
the always-on machine, this now answers the question:

```bash
python -m secondshift.evals status
```

Two guards close behind it. `score` compares the rubric it was handed against the
run's pinned hash before generating anything and refuses on a mismatch, so week 1
cannot be graded against a rubric it never used. And `deploy.sh` hashes the
target's rubric before the `rm -rf` and refuses to replace one that differs — an
edit made only on the machine was previously destroyed by the next deploy, which
would have changed the rubric out from under a pinned baseline with nothing
surfacing it. The rubric's own opening line is the rule: never edit in place;
supersede with `rubric-v2.md`.

**Still open, and a decision rather than an implementation:** which value the
baseline actually pinned, and if it is `4a7c2e91b3d0`, whether to re-record week
1 under the committed rubric. That needs the machine, and the re-record question
belongs to the person being measured. The brain is days old, so re-recording is
cheap now and never again.

### 4. `local-inference` — shipped 2 Sep

vLLM serving Nemotron 3.5 Lightning, implementing `Reasoner` against the
existing interface.

**Decided:** model bindings in ADR 0006 and `docs/MODELS.md`; NVFP4 with DSpark
speculative decoding; the base class already owns telemetry, so this
implements `_do_complete` only.

**Resolved by Spike B, 27 Aug** — the configuration question, not the
capability. NVFP4 at `--gpu-memory-utilization 0.30` with a 65k context limit
holds 43 GiB and leaves 77 free, and is *faster* at 3 concurrent than the
recommended 0.85, which consumed 112 of 121 GiB and left no room for ASR or the
embedder. Co-residency is therefore answered for the reasoner; MagpieTTS adds
1.85 GiB on top (Spike C), and ASR is unmeasured. Full detail in
`scripts/spikes/spike-b-local-inference/FINDINGS.md`.

**Shipped.** `VllmReasoner` implements `_do_complete` over the OpenAI-compatible
endpoint with the standard library, and the registry binds it on every local
profile — `cloud` keeps the placeholder, which is `nebius-executor`'s. A local
profile with no served-model name configured is now refused rather than quietly
echoed, because a registry that substitutes a placeholder for a missing backend
is what produced a system that answered without a model.

Both carried-over items are handled. The served model's visible chain-of-thought
is read from `reasoning_content` where vLLM's parser separates it and returned
whole where it does not — no marker-string splitter, which would delete the
answer whenever it guessed wrong. And `deploy/spark/second-shift-reasoner.service`
supervises the container, restarts it, and publishes it on 8200 rather than the
contested 8000 the spike served on.

Two telemetry gaps closed with it, both only reachable once a backend could fail:
a call whose backend raised recorded nothing at all, and a completion truncated
at the token limit was indistinguishable from a finished one.

**Not verified from a development window.** No call has reached the real server —
the provider is exercised against a stub speaking the endpoint's documented
shape, and the units are checked for agreement with `config/models.toml` rather
than started. The first real completion on the machine is where the remaining
risk sits.

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
- ~~Per-token rates for Lightning and Ultra in `config/pricing.toml`.~~
  **Resolved 27 Aug, hours after this entry was written.** Lightning, Super and
  Ultra were all read from the Token Factory console for `eu-north1`, standard
  and Batch, and are in `config/pricing.toml`. That supersedes both problems
  this bullet described: the blended figures never had to be split, and Super no
  longer rests on a third-party aggregator. The Batch rows are exactly half of
  standard, matching the tariff structure recorded below. A rate that is missing
  still fails loudly — none is missing today.
- Resolution of the judge deployment target.

**Decided:** ADR 0004 — build stage fans out to parallel variants, one job each;
`Executor.dispatch` carries the telemetry descriptor; `JobResult` never carries
telemetry.

**Open:** the ingest transport and its authentication; retry and idempotency
when a job reports telemetry twice.

#### Pricing structure observed in the Token Factory console, 2026-08-27

Nemotron rows were not in the captured extract, but the tariff structure is
consistent enough across the eleven models that were to be worth designing
against.

- **Batch is exactly 50% of standard**, input and output, across every model
  observed — DeepSeek R1/V3/V3.2/V4, Devstral, Cosmos3, even FLUX per-image.
  Zero exceptions.
- **`-fast` variants cost roughly 2.5x standard** (DeepSeek-R1 $0.80/$2.40
  against fast at $2.00/$6.00).
- **Output is consistently 2-3x input.** Completion-heavy stages dominate cost,
  so a verbose critic is expensive in a way a long prompt is not.
- Region is `eu-north1`. Every cloud call crosses the Atlantic from the Spark.
- **Dedicated endpoints bill by GPU hour**: H100 $4.05, H200 $4.70, B200 $7.40,
  B300 $8.10, L40S $2.00. This is a real answer to the judge-hosting question —
  a dedicated endpoint is rentable by the hour rather than requiring a serverless
  app target.

**The design consequence: the night pipeline should use the Batch API.**
Overnight work is the definition of batchable — nothing waits on a 2am run, and
the trans-Atlantic latency that would make batching painful for interactive work
is irrelevant when the deadline is morning. If Nemotron follows the observed
tariff, this halves cloud spend on every night, and cost per accepted artifact
is a scored chart.

The morning interview is the exception and must stay on the standard API: a
person is waiting.

This needs confirming for Nemotron specifically before it is built on, and it
changes what `Executor` and the cloud `Reasoner` look like — a batch submission
is submit-then-poll, not request-response.

### 6. `synthetic-seed` — shipped 28 Aug

The night generator. Unblocks all frontend work and seeds the judge instance.

**Decided:** every row carries `is_synthetic = 1`; rollup views already exclude
it; a full night is roughly six hours and 400+ events across lanes.

**Shipped and measured.** `python -m secondshift_seed --seed 42` writes one
run of 1,223 events over 7.3 hours across 7 lanes, 182 invocations at depth 3,
362 model calls with costs and latencies, and 6 failures. 1,019 events carry
`duration_ms` and render as bars; the rest are ticks. Every row is
`is_synthetic = 1` and the rollup views exclude them. Deterministic by seed, so
a screenshot is reproducible.

**Still open:** how realistic the generated *content* must be to be worth
screenshotting. The shape is dense enough to build against; whether the prose
inside an artifact survives a judge reading it closely is unanswered, and is a
question for `night-timeline` to raise once something renders it.

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
| `morning-interview` | Briefing from the log delta, then queued questions. The product. Includes the speech visualization below. |
| `retrieval` | Local embedding, assembly, policy filtering before egress. Brute-force cosine per ADR 0002. |
| `research` | Tavily search, extract, crawl. Redaction before any query leaves; credit accounting. |
| `artifacts` | Briefs, mockups, builds. Variant grouping and critic ranking; outcome capture. |
| `judge-mode` | The demo instance: cloud profile, synthetic persona, labeled in-UI, "run the night". |

---

## Speech visualization for the morning interview

Decided 28 Aug: the interview renders live audio, and it splits into two halves
with very different risk.

**Your speech is buildable now.** `getUserMedia` plus an `AnalyserNode` gives
real-time frequency and amplitude data with no dependency on anything unproven —
Spike A already confirmed `getUserMedia` passes on the phone.

**Its speech no longer waits on TTS.** MagpieTTS was verified on the Spark on
2026-08-28 — five fixed voices, RTF ~0.44, 22.05 kHz. TTS output is audio, and
the same `AnalyserNode` reads it through `createMediaElementSource`. One
component, two sources, and both sources now exist.

**What it must show to be worth building.** A bouncing waveform is decoration and
every demo has one. The version that earns its place visualizes the *turn-taking
machinery*:

- who holds the turn, and whether the system is listening or thinking
- **the moment end-of-utterance fires** — Parakeet Realtime EOU decides this in
  80–160ms, and that decision is the genuinely hard part of push-to-talk
- the gap between speech ending and a response starting, which is the latency a
  person actually feels

That makes it evidence of a working system rather than an animation over one, and
it is the same argument that makes the night scrubber worth building.

**Sequencing.** The input half belongs with `morning-interview`. The output half
is no longer gated on the TTS spike, but must still never block the interview
shipping — the
constitution's text-first principle means every voice interaction has a working
text equivalent, and a visualization of speech that does not exist is not an
exception to that.

## Ordering rule

`capture` before everything, because day-3 dogfooding starts a clock that cannot
be restarted. `nebius-executor` before any cloud reasoning, because the pricing
placeholders make every cloud call fail until it lands. `synthetic-seed` before
`night-timeline`, because a scrubber cannot be built against three events.
