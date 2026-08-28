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

## Day 1 — Thu 27 Aug — Foundations ✅ COMPLETE

**Baseline:** 79 tests, ~0.24s, arm64 / Darwin / Python 3.14.6. Recorded here
rather than in the failure ledger: that table is typed for failures and is
queried by the planner at planning time, so a timing row would pollute the
thing it exists to inform.

**What changed for later days:**

- `check_same_thread` had to be disabled on the SQLite connection. Threaded
  work records its own telemetry, and out-of-process telemetry ingests through
  the same connection; serialization is the recorder's lock. Anything writing
  outside `Recorder` must take that lock — relevant to the day-2 API.
- `pricing.toml`, not `pricing.yaml`. `tomllib` is stdlib from 3.11 and this
  project cannot afford another wheel on aarch64. **Cloud rates are
  placeholders and every cloud call will fail loudly until day 5 replaces
  them** — that is deliberate, but it means the first Token Factory call is
  blocked on real pricing.
- Quarantine is derived from the current capability report, not stored as
  status. Release is therefore automatic, and no migration was needed to add a
  status value.
- **Verified on the Spark** (Ubuntu 24.04.4, aarch64, Python
  3.12.3): 79/79 passing, ~2.75s. Local dev is Python 3.14 — the Spark's 3.12 is
  the target, and it stays there. Upgrading it would forfeit prebuilt aarch64
  wheels for vLLM, NeMo and torch, which is the landmine the whole plan avoids.
- The live probe on real hardware reports `cuda: available`, reasoner
  unreachable, speech stack absent — so the Spark today resolves to `cloud`,
  `degraded=True`, and would quarantine `local-only` entries naming both true
  causes. The degradation path is confirmed working before it is needed.
- `nvidia-smi` resolves at `/usr/bin/nvidia-smi` under a stripped environment,
  so the probe works from a systemd unit. This was the suspected day-1 bug; it
  is not present.
- **Tailscale SSH check-mode blocks scripted access.** Every attempt mints a new
  browser approval URL and expires on its own schedule regardless of the ssh
  client's timeout. Direct SSH over the LAN with key auth works and is what
  deploys should use. Worth settling before day 4.
- Two defects found only by running on a second machine: `constraints.txt`
  pinned an uninstallable pair, and macOS `tar` AppleDouble sidecars broke both
  migration discovery and the source scan. Transfers to the Spark need
  `COPYFILE_DISABLE=1`.


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

## Before day 3 — four things that do not exist yet

Found by checking rather than assuming, on 2026-08-27.

### 1. Offline capture needs TLS, so Spike A moves earlier

Service workers require a secure context — HTTPS, or `localhost`. A phone
reaching `http://<host>:8000` over the tailnet is neither. Without a service
worker there is no cached app shell, so **the app cannot load with no network,
and therefore cannot capture offline at all.** IndexedDB works over plain HTTP,
but only once the page has loaded, which is exactly what fails.

The earlier claim that "text capture needs no HTTPS" was true only about the
microphone. It is wrong about the PWA, and `capture`'s "succeeds without a
network" requirement depends on it.

**Spike A moves to day 2, alongside the PWA work.** It now blocks two things
rather than one: offline capture now, and the microphone later. The `mkcert`
fallback in its abort ladder also produces a secure context and remains valid.

### 2. The brain repository does not exist

ADR 0001 specifies a sibling repository. Nothing has created it, locally or on
GitHub, and day 3 requires committing entries to it.

**It must be private.** The code repository went public on 2026-08-27; the brain
holds captured ideas and a personal profile. Decide before day 3 whether it is
GitHub-private or local-only with its own backup — publishing it by accident is
not a recoverable mistake.

### 3. The five eval prompts and the rubric do not exist

Day 3's gate requires them fixed and committed. They measure getting better at
being *you*, so they need your judgment rather than a plausible draft.

### 4. Nothing runs the API persistently

`deploy/` does not exist and `add-capture` has no task that serves the app.
"Every idea from today forward, no exceptions" needs a service that is up when
an idea arrives and survives a reboot — a systemd unit on the Spark, bound
through Tailscale Serve. Capture builds the application; nothing yet runs it.

---

## Day 3 — Sat 29 Aug — 🚩 DOGFOODING STARTS

Wire capture to the brain repo: every entry appends to the dated journal and
commits. Record the eval baseline's **inputs** — no model exists yet, so this
records what cannot be reconstructed later and defers scoring to day 5.

**Pass gate**
- Every idea from today forward is captured in the real system. No exceptions,
  no notes app.
- The five held-out prompts and the rubric are fixed and committed.
- An `eval_runs` row exists pinning `rubric_sha` and the day-3 `brain_sha`.
- The brain's topic files exist and are non-empty, so week 1 is a real baseline
  rather than an empty one.

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

## Day 4 — Sun 30 Aug — Spike B: vLLM + Nemotron 3.5 Lightning on the Spark

**Downgraded from the highest-risk item on the critical path.** NVIDIA publishes
an official vLLM recipe naming **DGX Spark (GB10)** as a supported target, and
ships a speculative-decoding variant literally called **DSpark** — "preferred on
DGX Spark for latency." The aarch64 work has been done upstream.

The risk is no longer *will it run*. It is *which quantization and
speculative-decoding configuration*, which is tuning, not porting.

Serve `nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-NVFP4` on vLLM ≥ 0.27.1 with
DSpark speculative decoding.

**Pass gate** — OpenAI-compatible endpoint answers 3 concurrent requests, stable
over 30 minutes, tokens/sec recorded as a baseline in the failure ledger.
Resident memory leaves headroom for ASR and the embedder.

**Abort criteria** — timebox **half a day**, down from 1.5. Fall back in order:
1. NVFP4 without DSpark speculative decoding — throughput over latency
2. BF16 reference checkpoint if the quantized path misbehaves (roughly 60GB
   resident; verify headroom before committing)
3. Route reasoning to Token Factory and reframe `local-only` as *deferred*

Option 3 materially weakens the Airlock story. If it comes into play, escalate
rather than absorbing it quietly.

**Memory note:** a MoE model holds *all* 30B parameters resident. "3B active" is
a compute figure, not a memory one. NVFP4 is the default deployment target for
exactly this reason.

**The freed day is banked as slack.** A week-one plan with zero slack fails on
first contact. If it survives to Wednesday unspent, pull the seed generator
forward — it unblocks the most downstream work.

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

**Also on day 5 — score the week-1 eval baseline.** Generate and score the five
prompts against the `brain_sha` recorded on day 3, not against HEAD. Pinning to
the recorded SHA is the entire point of splitting the baseline, and it is the
one step that can silently go wrong and quietly weaken the eight-week delta.

**Pass gate** — both calls succeed with telemetry rows; the judge-hosting
question has a written answer in `docs/decisions/`; `eval_results` rows exist
for 5 prompts × 3 samples, linked to the day-3 `brain_sha`.

**Abort criteria** — if Serverless Jobs are unusable, the build stage runs local
and Nebius usage narrows to Token Factory. That still satisfies the rules but
weakens the Technological Implementation score. Knowing on day 5 leaves time to
redesign; knowing in week 6 does not.

---

## Day 6 — Tue 1 Sep — Spike D: Nemotron Speech on aarch64 + synthetic night generator

**ASR** — timebox half a day. Target is
`nvidia/nemotron-speech-streaming-en-0.6b`, not Parakeet TDT 1.1B: it is the
current packaging of the same cache-aware streaming Parakeet FastConformer
encoder, at roughly half the size, with streaming and punctuation built in —
better suited to push-to-talk than a batch model.
Pass gate: 60s of phone audio transcribes at acceptable WER, resident alongside
vLLM without OOM, latency recorded.
Abort: fall back to (1) an aarch64 NeMo container image, (2) Parakeet TDT 1.1B,
(3) defer voice. Text capture is already live, so this never blocks anything.
NeMo wheels on ARM remain the real risk here — keep the timebox honest.

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

**TTS.** Still not week one — but the odds improved. MagpieTTS ships inside NeMo
Speech, the same dependency stack the ASR spike already installs, so it is no
longer an orphan dependency with its own porting risk. Timeboxed half-day in
week 3. If it does not build, text-only briefings ship and nothing is lost.

**The celestial layer.** Week 6, after the scrubber works. It is worth real time
— but only once, and only on a foundation that already renders.

---

## Week-one failure condition

If capture-from-phone → logged entry is not working end to end by end of day
Wed 2 Sep, **stop every spike and fix only that.** Local model serving, Nebius
integration, and the scrubber are all recoverable in week two. A memory history
that starts late is not recoverable at all.
