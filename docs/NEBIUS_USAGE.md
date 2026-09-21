# What runs on Nebius, and why that split

**Evidence for the Technological Implementation criterion.** A day-7 deliverable
in `docs/WEEK_ONE.md` that did not happen, and then an entry in
`docs/ARCHITECTURE.md`'s directory tree asserting a file nobody had written —
which the drift pass of 16 Sep removed, on the grounds that a tree is not the
place to record an intention. It was absent for five weeks. Written 21 Sep.

**Read the status column before the numbers.** Some of what follows is
recorded, some is designed and not yet run. Every figure says which, and every
figure names the query or the file that produces it, because a number a reader
cannot reproduce is an adjective with digits.

---

## The split

`docs/decisions/0004-nebius-workload-split.md` settles it. The reasoning is not
"use the sponsor's cloud" — it is which work one DGX Spark genuinely cannot do.

| Where | What | Why there |
|---|---|---|
| **Always local, every profile** | Capture, ASR, transcript storage, embedding and retrieval, redaction and policy resolution, the orchestrator and every database write, the UI, and all reasoning for `local-only` entries. | The Privacy Airlock is an invariant, not a configuration. Retrieval stays local on every profile so that only assembled, policy-filtered context is ever eligible to leave. |
| **Token Factory** | The research-synthesis, architect and critic turns, on `cloud-assisted` entries only. | Long-context work against a high quality bar, where a 3B-active local model is the wrong tool rather than a slower one. |
| **Serverless Jobs** | The build stage, fanned out to three to five parallel variants — one Job each — ranked afterward by the critic into a `variant_group`. | **This is the argument.** One box cannot run five builds at once. The parallelism is not a speed-up; it is why the artifact is better, because the critic gets alternatives to choose between instead of one draft to accept. |
| **Nebius hosting** | The judge instance, on the `cloud` profile. | `docs/decisions/0009` — a no-GPU Serverless AI Endpoint, chosen because a judge instance cannot tolerate being preempted mid-demo. |

**What deliberately does not run there.** The brain never leaves the machine.
`model_call_payloads` never leaves the machine. A `local-only` idea never
reaches a remote provider — enforced as a `CHECK` constraint on `model_calls`,
so a code path that would violate it fails at the database rather than at a
review.

## Every model in the runtime path is an NVIDIA open model

A hackathon rule, and a stronger answer than one Nemotron call bolted to a
generic stack. `docs/MODELS.md` is the authority; this is the binding per role.

| Role | Model | Where |
|---|---|---|
| Reasoner | `nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-NVFP4` | Local, 30B MoE / 3B active |
| Speculative decoding | the same checkpoint's `-DSpark` variant | Local |
| ASR | `nvidia/nemotron-speech-streaming-en-0.6b` | Local |
| Turn-taking | Parakeet Realtime EOU | Local |
| Embedder | `nvidia/llama-nemotron-embed-vl-1b-v2` | Local |
| TTS | `nvidia/magpie_tts_multilingual_357m` | Local, verified on the GB10 on 28 Aug |
| Routine cloud turns | `Nemotron-3.5-Lightning` | Token Factory |
| Deep reasoning | `Nvidia-Nemotron-3-Super-120B-A12B` | Token Factory |
| Frontier turns, eval judge | `Nemotron-3-Ultra-550B-a55B` | Token Factory |

No third-party model is in the runtime path. The development of this repository
used one; the product does not.

## What a cloud night costs, and how you can check

Rates are in `config/pricing.toml`, read from the Token Factory console on
27 Aug, region `eu-north1`. They are git-tracked so a historical cost curve is
reproducible from the repository alone, and a rate that does not exist raises
`MissingRate` mid-run rather than recording a silent zero — understating a
scored measurement is worse than stopping.

| Model | Input $/Mtok | Output $/Mtok |
|---|---|---|
| Local (any) | 0.00 | 0.00 |
| `Nemotron-3.5-Lightning` | 0.06 | 0.24 |
| `Nvidia-Nemotron-3-Super-120B-A12B` | 0.30 | 0.90 |
| `Nemotron-3-Ultra-550B-a55B` | 1.00 | 3.00 |

Batch is exactly half of standard across every model observed, and
`config/pricing.toml` carries both. **A Token Factory key checked on 2 Sep found
Batch unavailable for these models**, so the Batch rates are recorded and unused.

Costs are **views over recorded rows, never stored numbers**:

```sql
SELECT * FROM night_totals;              -- local vs cloud tokens, per night
SELECT * FROM run_cost;                  -- per run, with tool credits
SELECT * FROM cost_per_accepted_artifact;-- spend per artifact a person kept
```

`night_totals` is the Privacy Airlock as a chart: a `local-only` night shows
`cloud_tokens = 0`, and it shows it because no row exists rather than because a
filter hid one. Every view excludes `is_synthetic = 1`, so a demo deployment's
rows can never reach a measurement.

## Status, honestly

| Claim | Status | Evidence, when it exists |
|---|---|---|
| The split above is designed and specified | **Recorded** | ADR 0004, ADR 0009, `openspec/specs/compute-profiles/`, `openspec/specs/privacy-airlock/` |
| A `local-only` idea cannot reach a remote provider | **Recorded and enforced** | The `model_calls` CHECK constraint in `0001_initial.sql`; `test_profile_airlock.py` |
| Token Factory credentials work end to end | **Verified 2 Sep** | A hand-built RS256 JWT exchanged for an access token, which then authorized `GET /ai/v1/jobs` with a 200. The private key never left the always-on machine. |
| Batch is unavailable for these models | **Verified 2 Sep** | Console check; rates recorded and unused |
| Nights run locally, end to end | **Recorded 16–17 Sep** | Two real nights on the Spark against the live reasoner; the second completed five stages in 192 seconds, and a later one completed six of six with research on |
| **A build stage fanned out to real parallel Jobs** | **Not yet run** | `SELECT count(*), sum(total_tokens), sum(estimated_cost_usd) FROM model_calls WHERE provider = 'nebius-job' AND is_synthetic = 0` — returns nothing today. **The `is_synthetic = 0` is not decoration**: the seeded night writes ten `nebius-job` rows, and the first draft of this table omitted the filter and would have shown a reader a fan-out that never happened |
| **A cloud night's cost, side by side with a local one** | **Not yet run** | `SELECT * FROM night_totals` — the demo's two-ideas comparison reads exactly this |
| **The week-1 to week-8 eval curve** | **Baseline recorded, not scored** | `python -m secondshift.evals curve` — says "nothing to compare yet" today, and will refuse five ways if the comparison would mean something other than it looks like |

**The three unrun rows are one blocker, not three.** The Nebius credentials
exist and were verified; they live on the always-on machine, outside any
git-tracked path. What is missing is a session on that machine, which
`docs/SPEC_ROADMAP.md` tracks under "what a machine session owes".

`openspec/changes/2026-09-02-add-nebius-executor/tasks.md` is the list that
session works. Its first hard stop is worth quoting, because it is the reason
this document has holes in it rather than numbers:

> a stub executor returning plausible job results is indistinguishable in
> `model_calls` from a real fan-out, and the fan-out is the entire evidence for
> the Nebius claim.

A stub would have filled this table. It would also have made every number in it
a fabrication, and the tables above are meant to be checkable.

## What is reproducible today, by anyone

A judge with a clone and no credentials can run all of this:

```bash
python3 scripts/gate.py                        # ten gates, about 100 seconds
apps/api/.venv/bin/python -m secondshift_seed --seed 42 --db /tmp/night.db
```

The synthetic night is **deterministic by seed**, so every screenshot in the
submission regenerates from the same command. It is also marked: every row it
writes carries `is_synthetic = 1`, every view excludes those rows, and
`scripts/check-judge-package.py` refuses to package a database that carries
unmarked ones or any `model_call_payloads` at all.

## The failure record is part of the argument

`scripts/spikes/*/FINDINGS.md` holds four spikes, two of which found that a
first-party published recipe did not run on the version it named —
`--moe-backend marlin` refused for this checkpoint's mixed FP8/NVFP4 MoE, and
`num_speculative_tokens` rejected without an explicit method. The
`failure_ledger` view is a first-class table, not a log file. The week-1 eval
baseline was recorded five days late and its `week_of` says so.

None of that is tidied, and it is not left in by neglect. A system that records
its own failures is making a claim a polished one cannot.
