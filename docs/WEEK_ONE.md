# Week One — Thu 27 Aug to Wed 2 Sep 2026

64 days to the deadline (Fri 30 Oct, 10:00 PT). Solo, so spikes run serially.
Ordering is by *blocking factor × risk*, not by interest.

## The one thing week one is for

> **Capture from phone → logged entry, working end to end, before week two.**

The submission's centerpiece is running a fixed prompt in week 1 and week 8 and
diffing the brain between them. That clock cannot be started retroactively.
Everything else in this plan is subordinate to it.

**The plan hits this on day 3 rather than week 2, using text capture only.**
Text capture needs no microphone, therefore no HTTPS, therefore no dependency on
the Tailscale spike. Real dogfooding starts Sat 29 Aug and the memory history
gains a full extra week. Voice upgrades the same path later without changing it.

---

## Day 1 — Thu 27 Aug — Foundations

Schema, telemetry recorder, provider interfaces, compute-profile resolution.
Telemetry is written before the first agent exists, because telemetry retrofitted
in week six has gaps exactly where the eight-week trend needs continuity.

**Pass gate**
- `schema.sql` applies clean; a test writes a `run` with nested
  `agent_invocations` (depth ≥ 2) and attached `model_calls`.
- The Airlock `CHECK` rejects a `local-only` + `token-factory` insert. *(Done —
  verified at design time.)*
- Profile resolution returns `cloud` on a machine with no CUDA.

**Abort criteria** — none. Unconditional; nothing proceeds without it.

---

## Day 2 — Fri 28 Aug — Capture API + minimal PWA

`POST /entries`, entry list, SSE stream. PWA shell: installable, text capture,
IndexedDB offline queue that drains on reconnect.

**Pass gate**
- Entry captured from the phone browser lands in SQLite with correct
  `captured_tz` and `tz_offset_min`.
- Airplane-mode capture queues locally and syncs on reconnect.

**Abort criteria** — if the PWA install/offline path fights back, ship a plain
responsive web page. Installability is polish; the logged entry is the gate.

---

## Day 3 — Sat 29 Aug — 🚩 DOGFOODING STARTS

Wire capture to the brain repo: every entry appends to a dated markdown file and
commits. Run the week-1 eval baseline — even with no orchestrator, the baseline
must exist now or the week-8 comparison has no left-hand side.

**Pass gate**
- Every idea from today forward is captured in the real system. No exceptions,
  no notes app.
- `eval_runs` row exists with `brain_sha`, `judge_model`, `rubric_sha` pinned.
- 5 prompts × 3 samples recorded.

**Abort criteria** — none. If this slips, the whole submission thesis slips with
it. Everything below yields to it.

---

## Day 3–4 — Sat 29 / Sun 30 — Spike A: Tailscale Serve TLS

Valid public TLS on the tailnet so mobile Safari/Chrome will expose
`navigator.mediaDevices`.

**Pass gate** — phone loads `https://<host>.<tailnet>.ts.net`, no cert warning,
`navigator.mediaDevices.getUserMedia` resolves, a 10-second recording uploads.

**Abort criteria** — timebox 1 day. Fall back in order: (1) `mkcert` CA
installed on the phone, (2) voice capture on desktop only, (3) defer voice
entirely. Text capture already works, so this spike blocks voice, not the
dogfooding gate. Do not let it eat the weekend.

---

## Day 4–5 — Sun 30 / Mon 31 — Spike B: vLLM + Nemotron Nano on sm_121

The highest-uncertainty item on the critical path. CUDA 13 / sm_121 / aarch64 is
a thin-support corner: no prebuilt flash-attn wheels, and anything pinning torch
below 2.6 will not support the architecture.

**Pass gate** — OpenAI-compatible endpoint answers 3 concurrent requests,
stable over 30 minutes, tokens/sec recorded in the failure ledger as a baseline.

**Abort criteria** — hard timebox 1.5 days. Fall back in order:
1. TensorRT-LLM
2. `llama.cpp` GGUF — loses continuous batching; acceptable at this concurrency
3. Route all reasoning to Token Factory and reframe `local-only` as *deferred*
   rather than *local*

Option 3 materially weakens the Airlock story, so if it comes into play,
escalate rather than absorbing it quietly.

---

## Day 5 — Mon 31 Aug — Spike C: Nebius round trip + judge-target resolution

Three deliverables, all small, all load-bearing:
1. One Token Factory completion with real token accounting written to
   `model_calls`.
2. One Serverless Job: dispatch → poll → retrieve an artifact.
3. **Resolve the judge deployment target.** Confirm whether Serverless
   Endpoints can host a Next.js + FastAPI application or whether a container/VM
   target is required. This is a submission-blocking assumption and it does not
   get to sit unexamined until week seven.

**Pass gate** — both calls succeed with telemetry rows; the judge-hosting
question has a written answer in `docs/decisions/`.

**Abort criteria** — if Serverless Jobs are unusable, the build stage runs local
and Nebius usage narrows to Token Factory. That still satisfies the rules but
weakens the Technological Implementation score. Knowing on day 5 leaves time to
redesign; knowing in week 6 does not.

---

## Day 6 — Tue 1 Sep — Spike D: Parakeet on aarch64 + synthetic night generator

**Parakeet** — timebox half a day.
Pass gate: 60s of phone audio transcribes at acceptable WER, resident alongside
vLLM without OOM, latency recorded.
Abort: fall back to (1) an aarch64 NeMo container image, (2) the smaller
`parakeet-tdt-0.6b-v2`, (3) defer voice. Text capture is already live, so this
never blocks anything.

**Synthetic night generator** — the highest-leverage item not in the original
brief. It generates a full 6-hour night: 400+ events across lanes, a nested
invocation tree, `model_calls` with realistic costs and latencies, 5 build
variants in a `variant_group` — everything flagged `is_synthetic = 1`.

Without it, the night scrubber cannot be developed for weeks, because real
nights will not produce dense data until the orchestrator exists. With it,
frontend work unblocks immediately and the judge instance's seed data is the
same code. Not throwaway.

**Pass gate** — generator produces a night that renders; all rows carry
`is_synthetic = 1`; rollup views exclude them.

---

## Day 7 — Wed 2 Sep — Night scrubber v0 + write-up

The signature component, built once and used three times (my night view, judge
mode's "run the night", the trend overlay's shared time axis).

**Pass gate** — scrub 6 hours of 400+ events at 20x holding 60fps; lanes render
per agent role; hovering an event surfaces the model call behind it.

**Abort criteria** — if 60fps is not reachable with DOM nodes, move to canvas.
Do not spend day 7 optimizing React reconciliation.

Also: ADRs committed, `NEBIUS_USAGE.md` started, week-two plan drafted from what
actually broke.

---

## Explicitly not in week one

**TTS.** Non-blocking by design and week one has no slack. Timeboxed half-day in
week 3. If Riva/Magpie does not build on aarch64, Piper; if Piper does not,
text-only briefings ship and nothing is lost.

**The celestial layer.** Week 6, after the scrubber works. It is worth real time
— but only once, and only on a foundation that already renders.

---

## Week-one failure condition

If capture-from-phone → logged entry is not working end to end by end of day
Wed 2 Sep, **stop every spike and fix only that.** Local model serving, Nebius
integration, and the scrubber are all recoverable in week two. A memory history
that starts late is not recoverable at all.
