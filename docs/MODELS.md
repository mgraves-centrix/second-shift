# Model Bindings

Every model in the runtime path is an NVIDIA open model. This is a hackathon
requirement and it is also, after checking the current lineup, the better
engineering choice — the Nemotron family now covers reasoning, ASR, TTS,
embedding and reranking, which collapses four vendor decisions into one.

Concrete bindings for `agents.default_model_local` and
`agents.default_model_cloud`.

## Local — `spark` profile

| Role | Model | Size | Notes |
|---|---|---|---|
| Reasoner | `nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-NVFP4` | 30B MoE / 3B active | Hybrid Mamba-MoE, distilled from Nemotron 3 Ultra, 1M context. vLLM ≥ 0.27.1. |
| Spec decoding | `...-NVFP4-DSpark` | — | Hybrid autoregressive + diffusion. NVIDIA's own note: preferred on DGX Spark for latency. |
| ASR | `nvidia/nemotron-speech-streaming-en-0.6b` | 0.6B | Streaming, punctuation + capitalization built in. |
| Turn-taking | Parakeet Realtime EOU | 120M | End-of-utterance detection at 80–160ms. |
| Embedder | `nvidia/llama-nemotron-embed-vl-1b-v2` | ~1.7B, 2048-dim | NVIDIA Open Model License, commercial use. |
| Reranker | `nvidia/llama-nemotron-rerank-1b-v2` | ~1.7B, 8192 seq | Optional, week 4+. |
| TTS | `nvidia/magpie_tts_multilingual_357m` | 357M | Verified on GB10 2026-08-28. RTF ~0.44, 1.85 GB. Five fixed voices. |

### Verified serving configuration, 2026-08-27

```
vllm/vllm-openai:v0.27.1   (has a linux/arm64 build)
nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-NVFP4
  --served-model-name nemotron-3.5-lightning
  --kv-cache-dtype fp8 --enable-prefix-caching
  --gpu-memory-utilization 0.30 --max-model-len 65536 --max-num-seqs 8
  --speculative-config '{"method":"mtp","num_speculative_tokens":3}'
```

48.6 tok/s median at 3 concurrent, 39.8 at 6, using 43 of 121 GiB.

Not from the model card's quick-start, which fails on the version it names:
`--moe-backend marlin` is refused for this checkpoint's mixed FP8/NVFP4 MoE, and
`num_speculative_tokens` needs an explicit `method`. See
`scripts/spikes/spike-b-local-inference/FINDINGS.md`.

**`--gpu-memory-utilization` is a fraction of the whole machine here.** The
recommended `0.85` leaves 9 GiB free and a 4.6M-token KV cache — no room for ASR
or the embedder, which is the reason NVFP4 was chosen. `0.30` leaves 77 GiB and
is faster at 3 concurrent.

**The served port is 8200, not the 8000 the spike used.** The container still
listens on vLLM's default 8000; the host publishes it on the port
`config/models.toml` allocates to the local reasoner and the capability probe
checks. The spike recorded 8000 as contested by an unrelated container, and a
port that depends on start order is not an allocation. `deploy/spark/second-shift-reasoner.service`
publishes it and is supervised, so the server survives a reboot — the spike left
it running with `--restart no`.

### Verified against the running server, 2026-09-02

First real calls, made over the tailnet against the live container (up 4 days,
serving `nemotron-3.5-lightning`, `max_model_len` 65536). Four things the spike
could not have known:

- **The reasoning is wrapped in `<think>...</think>` inline in `content`.** Not a
  prose marker — a structural delimiter. The `reasoning` field exists on the
  message and is `null`, because no reasoning parser is configured.
- **`usage` carries no `completion_tokens_details`.** Reasoning tokens are inside
  `completion_tokens` with no split available, so `reasoning_tokens` is honestly
  zero on every local call until a parser is enabled.
- **The reasoning can consume the whole completion budget.** "Reply with exactly:
  OK" spent 163 completion tokens, almost all of it deliberation. At
  `max_tokens=200` a one-sentence question hit `finish_reason: length` and
  returned reasoning with no answer at all. `reasoner_max_tokens` is not a
  length preference here; it is the budget the model thinks inside, and setting
  it too low returns nothing usable.
- **The container publishes on `0.0.0.0:8200`, not loopback**, and listens on
  8200 inside the container rather than vLLM's default 8000. Both differ from
  `deploy/spark/second-shift-reasoner.service`, which binds loopback and maps
  8200→8000. The unit is the safer shape; the running container predates it.

`--reasoning-parser` is the fix for the first two and remains **unverified for
this checkpoint**, so the unit still does not carry it. Verifying it costs a
container restart and about three minutes of model load.

**Visible chain-of-thought, and what has not been tried.** Every reply opens
"Here's a thinking process:". vLLM can separate that into a `reasoning_content`
field with `--reasoning-parser`, and the provider already reads that field and
its token count when they are present. **No parser has been verified for this
checkpoint**, so the units do not carry the flag: adding an unverified flag to a
first-party recipe is the exact trap this spike documented. Until one is
verified, the reasoning arrives inline and the provider returns it whole rather
than guessing where it ends.

### Why NVFP4 and not BF16

A MoE model must hold **all** parameters resident — the router can call any
expert on any token, so "3B active" is a compute figure, not a memory one. BF16
is roughly 60GB of weights; NVFP4 (W4A16) is roughly a quarter of that, and it
is NVIDIA's stated default deployment target. On 128GB unified memory that is
the difference between the reasoner sharing the box comfortably with ASR,
embeddings and a reranker, and it not sharing at all.

BF16 stays available as a reference checkpoint for output comparison.

### Verified TTS configuration, 2026-08-28

```
nvidia/magpie_tts_multilingual_357m        # public, not gated, no HF token
nvidia/nemo-nano-codec-22khz-1.89kbps-21.5fps   # pulled automatically
nemo_toolkit[tts] @ git+https://github.com/NVIDIA/NeMo.git@main   # 3.1.0+6281c939a
torch 2.13.0+cu130   # aarch64 wheel, cuda True on NVIDIA GB10
```

RTF ~0.44 steady state at 22.05 kHz mono, 1.85 GB resident, measured with the
reasoner container up. **Python must be pinned to 3.12** — NeMo's dependencies
cap at `<3.14`. `peft` is a real import-time dependency that `[tts]` omits.

**Exactly five voices, fixed, no cloning:**

| Voice | `speaker_index` |
|---|---|
| Aria | 0 |
| Jason | 1 |
| John | 2 |
| Leo | 3 |
| Sofia | 4 |

These are fixed speaker context embeddings — the model accepts no reference
audio, so the set cannot be extended without finetuning. 14 language tags:
`ar-AE ar-MSA ar-SA de en es fr hi it ja ko pt-BR vi zh`.

See `scripts/spikes/spike-c-tts-magpie/FINDINGS.md`.

## Cloud — Nebius Token Factory

| Role | Model | Notes |
|---|---|---|
Model ids are the exact Token Factory console identifiers, including case.
Every id guessed from the marketing name was wrong; these were read from the
console on 2026-08-27, region `eu-north1`. Rates are USD per 1M tokens.

| Role | Console model id | Input | Output |
|---|---|---|---|
| Routine turns | `Nemotron-3.5-Lightning` | $0.06 | $0.24 |
| Deep reasoning | `Nvidia-Nemotron-3-Super-120B-A12B` | $0.30 | $0.90 |
| Frontier turns, eval judge | `Nemotron-3-Ultra-550B-a55B` | $1.00 | $3.00 |

Every model also has a `-Batch` variant at **exactly half** both rates. The
eval judge is version-pinned in `eval_runs.judge_model_version` and never
floats.

### Batch for the night, standard for the morning

Batch pricing is 50% of standard across every model on the platform without
exception — verified over fourteen model pairs. The night pipeline is the
definition of batchable work: nothing waits on a 2am run, and the
trans-Atlantic hop to `eu-north1` that would make batching painful for
interactive work is irrelevant when the deadline is morning.

A representative cloud-assisted night — ten Lightning routine turns, three
Super synthesis turns, one Ultra critique — costs **$0.12 on the standard API
and $0.06 on batch**. Across the 63 nights to the deadline that is $7.67
against $3.84.

The saving is real but small in absolute terms; the reason to use batch is not
the money. It is that **cost per accepted artifact is a scored chart**, and
halving the denominator of the argument you are making is worth the submit-then-
poll complexity. The morning interview stays on the standard API, because a
person is waiting.

Batch changes the shape of the cloud `Reasoner`: submission and retrieval are
separate operations, not one call. That belongs in the `nebius-executor` spec
before it is built.

## The property worth exploiting

**Nemotron 3.5 Lightning runs both locally on the Spark and on Nebius Token
Factory.** The same model ID exists on both sides of the airlock.

That means the compute profile has identity at the *model* level, not just the
interface level. On the `cloud` profile, a Lightning call routes to Token
Factory instead of local vLLM — same model, same weights, different provider.

Two consequences:

1. The `cloud` profile is a genuine port of the product, not a degraded
   imitation of it. Only the privacy guarantee changes, and the UI says so.
2. The local-vs-cloud token chart becomes a clean infrastructure comparison
   rather than one confounded by model quality. When a `local-only` idea and a
   `cloud-assisted` idea produce different-quality artifacts, that difference is
   attributable to escalation to Super/Ultra and to parallel Jobs fan-out — not
   to a small model losing to a big one at the base tier.

## Escalation policy

```
local-only     → Lightning (local vLLM). Never escalates. Enforced by CHECK constraint.
cloud-assisted → Lightning for routine turns (local or Token Factory by profile)
               → Super for research synthesis, architect, critic
               → Ultra only when Super's critique output is rejected twice
```

Escalation is recorded in `model_calls.effort` and is visible per-idea in the
UI, so "why did this idea cost 40x that one" always has an answer on screen.

## Deliberately not used

- **NV-Embed-v2** — ~7.85B and CC-BY-NC-4.0. `llama-nemotron-embed-vl-1b-v2` is
  the same job from the same vendor at roughly a fifth the size under a
  commercial-use license. See `docs/decisions/0006`.
- **Parakeet TDT 1.1B** — not rejected so much as superseded by its own family.
  The cache-aware streaming Parakeet FastConformer encoder is what sits inside
  `nemotron-speech-streaming-en-0.6b`; the newer packaging is smaller, streams,
  and punctuates.
- **Any non-NVIDIA LLM in the runtime path** — rules, and scoring.

## To verify in week one

- License terms for Nemotron 3 Super and Ultra as served by Token Factory.
- Whether `nemotron-speech-streaming-en-0.6b` and the reasoner can be co-resident
  on the Spark under sustained load without contention.
- Current Token Factory catalog and per-token pricing, for
  `model_calls.estimated_cost_usd`. Pricing must be read from a config file,
  never hardcoded — the cost curve is a scored artifact.
