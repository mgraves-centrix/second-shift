# Second Shift

**The assistant that interrogates your idea before spending compute on it.**

Second Shift is an always-on personal assistant that turns half-formed ideas into
real artifacts overnight. You capture an idea by voice or text whenever you have
one. Overnight, a machine you own researches it and builds something. In the
morning you ask "what happened since we last talked," get a briefing — and then
it interviews you, asking the questions it got stuck on. Your answers become
tracked decisions that feed the next night's run.

Overnight agents are a commodity. The interview is the product.

Built for the Nebius x NVIDIA Global AI Hackathon, Personal AI track.

---

## Status

Day one. Nothing works yet. This README describes the target, not the present.

| Milestone | State |
|---|---|
| Repo scaffold | done |
| Capture path (PWA → ASR → logged entry) | not started |
| Night orchestrator | not started |
| Morning interview | not started |
| Night scrubber UI | not started |
| Judge demo instance | not started |

---

## The loop

```
capture ──▶ queue ──▶ night run ──▶ artifacts + open questions
   ▲                                          │
   │                                          ▼
decisions ◀────────────── morning interview ◀─┘
```

Each stage of the night run commits as it completes. If the 2am build stage
fails, morning still has the brief, the research, and the questions. Graceful
degradation is correct behavior, not a failure state.

---

## Scope

**Idea in, artifact out, memory in between.**

That boundary is load-bearing. See [NOT_BUILDING.md](NOT_BUILDING.md) for what
is deliberately excluded and why.

---

## Architecture principles

1. **The brain is a folder of plaintext under git.** Skills, style guide,
   failure ledger, profile — human-readable markdown, diffable across time.
   No opaque memory database.
2. **Privacy Airlock.** Every idea carries a policy set at capture:
   `local-only` (never leaves the machine) or `cloud-assisted` (redaction pass,
   then Nebius Token Factory). Retrieval always runs locally; only assembled,
   policy-filtered context is ever transmitted. The brain itself never leaves.
3. **No empty mornings.** The night pipeline is a checkpointed state machine.
   Every stage that completes is committed and presentable.
4. **Text-first, voice layered on.** Every voice interaction has a working text
   equivalent.
5. **Two deployments, one codebase.** Personal instance on owned hardware;
   judge instance on Nebius with a synthetic persona and zero real data,
   labeled in-UI as a demo.

---

## Stack

| Layer | Technology |
|---|---|
| Capture | PWA — Next.js / React, Web Audio API |
| ASR | Nemotron Speech Streaming 0.6B, local |
| Local reasoning | Nemotron 3.5 Lightning 30B A3B (NVFP4), vLLM |
| Cloud reasoning | Nemotron 3 Super / Ultra via Nebius Token Factory |
| Overnight compute | Nebius Serverless Jobs |
| Judge demo hosting | Nebius |
| Web research | Tavily |
| Embeddings | Llama Nemotron Embed VL 1B v2, local |
| Memory | Plaintext markdown + SQLite, git-versioned |
| Orchestrator | Python + FastAPI, SQLite job queue, systemd timers |
| Dashboard | Next.js + Tailwind, server-sent events |
| TTS | MagpieTTS via NeMo Speech — non-blocking |

Target hardware: NVIDIA DGX Spark (GB10 Grace Blackwell, 128GB unified memory,
aarch64, CUDA 13.0, sm_121).

Every model in the runtime path is an NVIDIA open model. See
[docs/MODELS.md](docs/MODELS.md) for exact bindings and
[THIRD_PARTY.md](THIRD_PARTY.md) for licenses.

---

## Telemetry

Every agent invocation and every model call is logged from run one — provider,
model, tokens, latency, cost, and the privacy policy it ran under. This is not
housekeeping. It is how the Privacy Airlock is proven rather than claimed
(local-only ideas consume visibly zero cloud tokens), and how "it gets better at
being me" becomes a measurable trend instead of an assertion.

---

## Getting started

Not yet. Setup instructions land once the capture path works.

---

## License

Apache License 2.0 — see [LICENSE](LICENSE) and [NOTICE](NOTICE).
