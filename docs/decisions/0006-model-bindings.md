# 0006 — Model bindings: the whole runtime path is Nemotron

**Status:** accepted · **Date:** 2026-08-27

## Context

Using NVIDIA models is a hackathon requirement, and judging weighs how
effectively Nemotron is used. Reviewing the current lineup rather than the one
assumed in the original brief changed several bindings, and resolved an open
license question by replacement rather than by argument.

The original brief named Nemotron Nano, Parakeet TDT 1.1B, and NV-Embed. All
three move.

## Decision

**Local (`spark`):**

- Reasoner: `nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-NVFP4`, vLLM ≥ 0.27.1,
  with DSpark speculative decoding. Hybrid Mamba-MoE, 30B total / 3B active,
  1M context, distilled from Nemotron 3 Ultra, OpenMDW-1.1 licensed.
- ASR: `nvidia/nemotron-speech-streaming-en-0.6b`
- Turn-taking: Parakeet Realtime EOU (120M), end-of-utterance at 80–160ms
- Embedder: `nvidia/llama-nemotron-embed-vl-1b-v2` (~1.7B, 2048-dim)
- Reranker: `nvidia/llama-nemotron-rerank-1b-v2` (optional, week 4+)
- TTS: MagpieTTS via NeMo Speech

**Cloud (Token Factory):** Nemotron 3 Super 120B A12B for deep reasoning,
Nemotron 3 Ultra 550B A55B for frontier turns and as the version-pinned eval
judge, Nemotron 3.5 Lightning for routine turns on the `cloud` profile.

## Rationale

**Lightning over Nano.** NVIDIA describes Lightning as the fastest 30B MoE for
*always-on agents*, which is a description of this product. It also has an
official vLLM recipe naming DGX Spark (GB10) as a target, and a
speculative-decoding variant named DSpark — NVIDIA's own note calls it preferred
on DGX Spark for latency. First-party support for the exact hardware is worth
more than any local benchmark.

**NVFP4 over BF16.** A MoE model holds all parameters resident; the router can
call any expert on any token, so "3B active" is a compute figure, not a memory
one. BF16 is roughly 60GB of weights against NVFP4's roughly quarter of that,
and NVFP4 (W4A16) is NVIDIA's stated default deployment target. On 128GB unified
this is the difference between the reasoner co-existing with ASR, embedder and
reranker, and it not.

**Nemotron Speech over Parakeet TDT 1.1B.** Not a rejection — a supersession
inside the same family. The cache-aware streaming Parakeet FastConformer encoder
is what sits inside the Nemotron Speech checkpoint. The newer packaging is
roughly half the size, streams, and punctuates, which suits push-to-talk better
than a batch model.

**Parakeet Realtime EOU is an unplanned win.** End-of-utterance detection at
80–160ms in 120M parameters is precisely the primitive push-to-talk turn-taking
needs, and it removes the temptation to reach for wake words — which
[NOT_BUILDING.md](../../NOT_BUILDING.md) rules out anyway.

**`llama-nemotron-embed-vl-1b-v2` over NV-Embed-v2.** NV-Embed-v2 is ~7.85B
under CC-BY-NC-4.0. The replacement is the same job, same vendor, roughly a
fifth the size, under the NVIDIA Open Model License with commercial use. The
open license question resolves by moving *toward* a newer NVIDIA model, not away
from NVIDIA.

## Consequences

**Lightning runs on both sides of the airlock** — locally on the Spark and on
Nebius Token Factory. The compute profile therefore has identity at the model
level, not just the interface level: on `cloud`, a Lightning call routes to Token
Factory instead of local vLLM with the same weights.

This makes the `cloud` profile a genuine port rather than a degraded imitation,
and it cleans up the headline chart — local-vs-cloud tokens becomes an
infrastructure comparison, not one confounded by model quality. Quality
differences between `local-only` and `cloud-assisted` ideas are then honestly
attributable to Super/Ultra escalation and Jobs fan-out.

**Week-one risk drops.** Spike B falls from 1.5 days to half a day, and from
"will vLLM build for sm_121" to "which quantization config." One day returns to
the schedule as slack.

**Every model in the runtime path is NVIDIA.** Reasoning, speech, embedding,
reranking, TTS. That is a stronger answer to the Technological Implementation
criterion than a single Nemotron call bolted onto a generic stack.

**Open:** license terms for Super and Ultra as served by Token Factory, and
Token Factory per-token pricing. Pricing is read from config, never hardcoded —
the cost curve is a scored artifact.
