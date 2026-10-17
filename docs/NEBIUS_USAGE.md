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

## Every model bound to a role is an NVIDIA open model

A hackathon rule, and a stronger answer than one Nemotron call bolted to a
generic stack. `docs/MODELS.md` is the authority; this is the binding per role —
**which is not the same as what has run.** Of the rows below, the local reasoner
and the embedder have produced output; the TTS model synthesized in its spike
without being wired in; ASR, turn-taking and every Token Factory row have not
run at all. The eval judge was a row here until 10 Oct, when
`docs/decisions/0015` moved it off Token Factory entirely — brain-derived text
cannot reach a remote provider, so a cloud judge was never permissible.

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
| Frontier turns | `Nemotron-3-Ultra-550B-a55B` | Token Factory |

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
filter hid one. The exclusion of generated data is on the run — `run_cost`
carries `WHERE r.is_synthetic = 0`, and the other two views are built on it — so
a demo deployment's rows cannot reach a measurement.

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
| **The week-1 to week-8 eval curve** | **Baseline recorded, not scored. The bar is fixed.** | `python -m secondshift.evals curve` — says "nothing to compare yet" today, refuses 11 <!-- derived: matches apps/api/secondshift/evals/runner.py raise NotComparable\( --> ways if the comparison would mean something other than it looks like, and prints its verdict against `config/evals/threshold.md`, fixed 23 Sep while no week-8 output existed |

**They are not one blocker, and this said they were until 16 Oct.** The
credentials exist and were verified, and they live on the always-on machine
outside any git-tracked path — but the three rows wait on different things:

- **The fan-out and the cost comparison** need the credential *and* a client
  nobody has written. `providers/` contains no Nebius module, and
  `openspec/changes/2026-09-02-add-nebius-executor/` stands at 3 of 23 tasks.
- **The eval curve** needs no credential at all, since `docs/decisions/0015`
  made the judge local on 10 Oct. It needs a session on the machine, because the
  database, the brain and the model are all there.

`docs/SPEC_ROADMAP.md` tracks each under "what a machine session owes".

`openspec/changes/2026-09-02-add-nebius-executor/tasks.md` is the list that
session works. The hard stop behind it is worth quoting, because it is the
reason this document has holes in it rather than numbers — from
`docs/prompts/NEBIUS_EXECUTOR.md`, which is where the sentence actually lives;
this document attributed it to the task list until 16 Oct:

> a stub executor returning plausible job results is indistinguishable in
> `model_calls` from a real fan-out, and the fan-out is the entire evidence for
> the Nebius claim.

A stub would have filled this table. It would also have made every number in it
a fabrication, and the tables above are meant to be checkable.

## What is reproducible today, by anyone

No credentials and no access to the always-on machine. A bootstrap first,
because both commands below run inside a virtual environment a fresh clone does
not have — `docs/development/GATES.md` has the clean-clone section, and the gate
refuses by name rather than guessing when it is missing:

```bash
python3 -m venv apps/api/.venv
apps/api/.venv/bin/pip install -c apps/api/constraints.txt -e "apps/api[dev]" -e packages/seed
npm --prefix apps/web ci

python3 scripts/gate.py       # every gate; around five minutes and growing
apps/api/.venv/bin/python -m secondshift_seed --seed 42 --db /tmp/night.db
```

The duration is deliberately not quoted precisely: most of it is the mutation
list, which grows every time a defect ships. It read "two minutes" here while
the mutations alone took three.

The synthetic night is **deterministic by seed** — the same run id, the same
1,232 events, every time — so any screenshot shown alongside the submission
regenerates rather than being a picture of a state nobody else can reach. There
are no images in this repository.

It is also marked: every row it writes carries `is_synthetic = 1`, the exclusion
is on the run (`run_cost` carries `WHERE r.is_synthetic = 0` and `night_totals`
is built on it), and `scripts/check-judge-package.py` refuses to package a
database that carries unmarked rows in an evidence table or any
`model_call_payloads` at all.

## The bar was set before the number

`config/evals/threshold.md`, fixed **23 Sep 2026**, when the only eval run in
the system had `judge_model = 'awaiting-scoring'` and there was nothing to be
influenced by.

An improvement is **both**: the mean per-prompt change exceeding twice its
standard error across the active prompts, and at least two thirds of them moving
that way. Anything else is *no improvement shown* — which the file is careful to
distinguish from *the brain learned nothing*, because six prompts cannot support
the negative claim either.

Two things make that checkable rather than assertable. The file's addition is in
the history — `git log --diff-filter=A -- config/evals/threshold.md` against the
commit that records the run — and its content hash is printed beside the verdict
every time the curve runs, so an edit after the fact is visible in the one place
somebody reads the result.

**The bar is applied by the same command that reports the result**, so a
favorable number and an unfavorable one go through identical arithmetic. If it
comes out the other way, the submission says the brain got worse, with the same
prominence.

## The failure record is part of the argument

Four spikes ran, and three left a `FINDINGS.md` — spike A's write-up is its
`README.md`, beside the harness it served. Two of them found that a first-party
published recipe did not run on the version it named —
`--moe-backend marlin` refused for this checkpoint's mixed FP8/NVFP4 MoE, and
`num_speculative_tokens` rejected without an explicit method. The
`failure_ledger` is a view over typed rows rather than a log file, so a failure
is queryable beside the run that produced it. The week-1 eval
baseline was recorded five days late and its `week_of` says so.

None of that is tidied, and it is not left in by neglect. A system that records
its own failures is making a claim a polished one cannot.
