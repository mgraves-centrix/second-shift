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

## Spike letters

The letters below are the ones the harnesses in `scripts/spikes/` actually
carry, which is what `docs/SPEC_ROADMAP.md` and the prompts in `docs/prompts/`
cite. They are not the letters this plan assigned on 27 Aug: spikes ran out of
order, two of the planned four were never run, and two that were not in the plan
were. C and D were reassigned by what got built rather than by what was
scheduled, so the two planned entries they displaced are now E and F.

| | Question | Where |
|---|---|---|
| **A** | Secure context over Tailscale Serve | `scripts/spikes/spike-a-secure-context/` — passed 27 Aug |
| **B** | Serving Nemotron 3.5 Lightning on the Spark | `scripts/spikes/spike-b-local-inference/` — passed 27 Aug |
| **C** | MagpieTTS on aarch64 + Blackwell | `scripts/spikes/spike-c-tts-magpie/` — passed 28 Aug |
| **D** | DOM or canvas for the night scrubber | `scripts/spikes/spike-d-scrubber-rendering/` — DOM, 2 Sep |
| **E** | Nebius round trip + judge-target resolution | day 5 below — **1 of 3**: the target is resolved (`docs/decisions/0009`); credentials reach the real API, but no completion and no job have been recorded |
| **F** | Nemotron Speech (ASR) on aarch64 | day 6 below — **not run**. The other half of day 6, the synthetic night generator, shipped as `packages/seed/` |

A letter with no directory under `scripts/spikes/` was not run. Do not read a
plan entry as evidence that its spike happened.

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
- the migrations apply clean; a test writes a `run` with nested
  `agent_invocations` (depth ≥ 2) and attached `model_calls`.
- The Airlock `CHECK` rejects a `local-only` + `token-factory` insert. *(Done —
  verified at design time.)*
- Profile resolution returns `cloud` on a machine with no CUDA.

**Abort criteria** — none. Unconditional; nothing proceeds without it.

---

## Day 2 — Fri 28 Aug — Capture API + minimal PWA ✅ SHIPPED

Live at **https://<host>.<tailnet>.ts.net** — the PWA and its API on one
origin, behind Tailscale Serve's certificate, running as a systemd **user**
service (no sudo needed to install it).

Verified end to end through the tailnet: an entry whose capture instant was
three days before receipt stored that instant, not the receipt; a replay
returned 200 with `duplicate: true` and created no second row; the title was
derived without a model; and `local-only` was stored as intent.

The API listens on **8080, not 8000** — a local vLLM server claims 8000, and the
capability probe should not have to distinguish two different things on one port.

**Two things still need doing, both requiring sudo:**

- `sudo loginctl enable-linger mgraves` — without it the user service does not
  start until someone logs in, and "every idea, no exceptions" means surviving a
  reboot unattended.
- Optionally install the system unit at `deploy/spark/second-shift-api.service`
  instead, which does the same without lingering.


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

### 1. Offline capture needs TLS — Spike A ✅ PASSED, 2026-08-27

Service workers require a secure context — HTTPS, or `localhost`. A phone
reaching `http://<host>:<port>` over the tailnet is neither. Without a service
worker there is no cached app shell, so **the app cannot load with no network,
and therefore cannot capture offline at all.** IndexedDB works over plain HTTP,
but only once the page has loaded, which is exactly what fails.

The earlier claim that "text capture needs no HTTPS" was true only about the
microphone. It is wrong about the PWA, and `capture`'s "succeeds without a
network" requirement depends on it.

**Spike A moves to day 2, alongside the PWA work.** It now blocks two things
rather than one: offline capture now, and the microphone later. The `mkcert`
fallback in its abort ladder also produces a secure context and remains valid.

**Result: passed on the real device, one day early.** All six checks green on an
iPhone against `https://<host>.<tailnet>.ts.net` — protocol,
`isSecureContext`, service worker present, IndexedDB, `getUserMedia`, and the
one that mattered: **the service worker actually registered**, scope
`https://<host>.<tailnet>.ts.net/`.

Certificate is Let's Encrypt, valid to 26 Nov 2026, validating with no override.

`getUserMedia` also passed. That was not the question asked, but it answers the
microphone half of the original day-3/4 spike at the same time — so the Spike A
slot on days 3-4 is now free.

Cost: about an hour, most of it blocked on a permission. Two preconditions that
are worth writing down because nothing surfaced them until they failed:
`sudo tailscale set --operator=$USER` on the box, and HTTPS Certificates
enabled for the tailnet in the admin console.

The harness is kept at `scripts/spikes/spike-a-secure-context/` rather than
deleted — it re-answers the question in one page load if TLS ever regresses, or
when Serve is repointed at the capture API.

**Carried forward:** Serve currently points at the static spike directory. The
capture API will need `tailscale serve --bg --https=443 http://127.0.0.1:<port>`
instead, and that port must not be 8000 — a restored Qwen container claims it.

### 2. The brain repository — done, local only

Created at `../second-shift-brain`, git-initialized, seeded and committed. Topic
files (`profile.md`, `style-guide.md`, `skills/`) are rewritten in place; the
journal is append-only. Seeded deliberately naive rather than empty, so the
week-8 diff shows refinement rather than accumulation from nothing.

**No remote is configured.** Nothing is published and nothing can be pushed by
accident. Whether it gets a private GitHub remote or stays local with its own
backup is still yours to decide — but it must never be public.

**It must be private.** The code repository went public on 2026-08-27; the brain
holds captured ideas and a personal profile. Decide before day 3 whether it is
GitHub-private or local-only with its own backup — publishing it by accident is
not a recoverable mistake.

### 3. The eval prompts and the rubric do not exist — resolved, five days late

`config/evals/rubric.md` and `config/evals/candidates.md` are committed. Ten
candidates were loaded and **six activated on 30 Aug** — not the five this plan
expected; five was an expectation, never a requirement, and six is what the
baseline pins. The rubric hashes to `b4decd6fe774` on disk and on the always-on
machine, byte-identical.

The baseline itself was not recorded until **2 Sep** — `seed` and `activate` ran
on 30 Aug, `baseline` did not. See the day-3 gate below for what that cost and
what could not be recovered.

### 4. Nothing runs the API persistently — resolved

`deploy/spark/` now holds a deploy script, a system unit and a user unit. The
user unit is installed and running; `loginctl enable-linger` is still needed for
it to start unattended after a reboot.

---

## 🚩 Dogfooding began early — 28 Aug

Capture went live a day ahead of plan and the first real entries were captured
from a phone the same night. One of them sat in the offline queue for **62.7
seconds** before draining — the first evidence the offline path works outside a
test, with the capture instant preserved rather than overwritten by the receipt
instant.

Idea content is not recorded here. It lives in the brain repository, which is
local-only.

**Note on the git history.** On 28 Aug the history was rewritten with
`git-filter-repo` to remove environment details — a private address, home paths,
a username in a unit file, and a tailnet hostname — that had accumulated across
five files in the day after the repository went public. Commit dates, messages
and ordering are unchanged; only the object SHAs differ, and one commit was
pruned because the rewrite made it empty. Anyone holding a clone from before
that point will not fast-forward.

The tailnet hostname remains in Certificate Transparency logs regardless: Let's
Encrypt publishes every name it issues for, so it was public before it ever
reached git. A rename, not a git operation, is the fix if that matters.

---

## Day 3 — Sat 29 Aug — first night run

Wire capture to the brain repo: every entry appends to the dated journal and
commits. Record the eval baseline's **inputs** — no model exists yet, so this
records what cannot be reconstructed later and defers scoring to day 5.

**Pass gate — two of four met on the day, one met late, one unrecoverable.**
- ✅ Every idea from today forward is captured in the real system. No exceptions,
  no notes app. Capture went live 28 Aug and has taken real entries since.
- ✅ The held-out prompts and the rubric are fixed and committed. (Six were
  activated on 30 Aug, not five; the number was an expectation, not a
  requirement.)
- ❌ **An `eval_runs` row exists pinning `rubric_sha` and the day-3 `brain_sha`.**
  No such row was written on day 3, or for five days after: `seed` and
  `activate` ran on 30 Aug and `baseline` did not, which nothing surfaced
  because nothing was reading `eval_runs`. A baseline was finally recorded on
  **2 Sep** — `01M1FYFECEXC5ZJEWHNP7WZMXB`, `week_of 2026-08-31`, rubric
  `b4decd6fe774`, brain `ad17b3bcddb6`, awaiting scoring. **It pins the 2 Sep
  brain, not the day-3 one.** The day-3 brain state is gone; the journal and the
  topic files moved on, and there is no honest way to reconstruct what they held
  on 29 Aug. The eight-week delta therefore measures seven weeks and change from
  a later floor, and the row says so rather than carrying a `week_of` that
  pretends otherwise.
- ✅ The brain's topic files exist and are non-empty, so week 1 is a real
  baseline rather than an empty one.

**Abort criteria** — none. If this slips, the whole submission thesis slips with
it. Everything below yields to it. *It slipped by five days and the thesis
survived, narrower: the comparison is still real, its floor is just later than
planned. That is the cost of a gate nothing was checking.*

---

## Day 3–4 — Sat 29 / Sun 30 — Spike A: Tailscale Serve TLS ✅ DONE 27 Aug

Completed early. See "Before day 3" above for the result. This slot is free —
the obvious use is pulling day-4's vLLM spike forward now that the Spark has
118 GiB available.

<details><summary>Original plan, kept for the record</summary>


Valid public TLS on the tailnet so mobile Safari/Chrome will expose
`navigator.mediaDevices`.

**Pass gate** — phone loads `https://<host>.<tailnet>.ts.net`, no cert warning,
`navigator.mediaDevices.getUserMedia` resolves, a 10-second recording uploads.

**Abort criteria** — timebox 1 day. Fall back in order: (1) `mkcert` CA
installed on the phone, (2) voice capture on desktop only, (3) defer voice
entirely.

</details>

---

## Day 4 — Sun 30 Aug — Spike B ✅ PASSED 27 Aug

**Downgraded from the highest-risk item on the critical path.** NVIDIA publishes
an official vLLM recipe naming **DGX Spark (GB10)** as a supported target, and
ships a speculative-decoding variant literally called **DSpark** — "preferred on
DGX Spark for latency." The aarch64 work has been done upstream.

The risk is no longer *will it run*. It is *which quantization and
speculative-decoding configuration*, which is tuning, not porting.

Serve `nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-NVFP4` on vLLM ≥ 0.27.1 with
DSpark speculative decoding.

**Result: passed, three days early.** 9/9 at 3 concurrent (median 48.6 tok/s,
5.3s) and 6/6 at 6 concurrent (39.8 tok/s, 6.4s). The probe then verified the
whole chain end to end against the real server: `cuda: available`,
`local_reasoner: available`, profile `workstation`, `local-only` available.
`workstation` rather than `spark` is correct — the speech stack is day 6 — and
profile resolution was written before any of this hardware ran.

Full detail: `scripts/spikes/spike-b-local-inference/FINDINGS.md`.

**Three findings worth carrying:**

1. **The published DGX Spark quick-start does not run on the vLLM version its
   own model card names.** `--speculative_config.num_speculative_tokens 3` is
   rejected without a `method`, and `--moe-backend marlin` is refused for this
   checkpoint's mixed FP8/NVFP4 MoE. Both are first-party instructions for this
   exact hardware. Budget configuration time for vendor recipes, not only for
   unproven paths.
2. **`--gpu-memory-utilization` takes a fraction of the whole machine on unified
   memory.** The recommended `0.85` consumed 112 of 121 GiB and built a
   4.6M-token KV cache, leaving no room for ASR or the embedder — which was the
   entire argument for NVFP4. At `0.30` with a 65k context limit it uses 43 GiB,
   leaves 77 free, and is *faster* at 3 concurrent.
3. **The model emits visible chain-of-thought.** Every reply opens "Here's a
   thinking process:". Agent prompts and the brief renderer both have to account
   for it.

**Left running** at the tuned configuration, with `--restart no` — it does not
survive a reboot. A systemd unit is part of the deployment work that
`add-capture` still lacks.

<details><summary>Original plan, kept for the record</summary>

**Pass gate** — OpenAI-compatible endpoint answers 3 concurrent requests, stable
over 30 minutes, tokens/sec recorded. Resident memory leaves headroom for ASR
and the embedder.

**Abort criteria** — timebox **half a day**, down from 1.5. Fall back in order:
1. NVFP4 without DSpark speculative decoding — throughput over latency
2. BF16 reference checkpoint if the quantized path misbehaves (roughly 60GB
   resident; verify headroom before committing)
3. Route reasoning to Token Factory and reframe `local-only` as *deferred*

Option 3 materially weakens the Airlock story. If it comes into play, escalate
rather than absorbing it quietly.

</details>

### Blocking finding, 2026-08-27: the Spark is not idle

The box is already serving **`Qwen/Qwen3.8-27B-FP8`** through vLLM in the
`vllm-qwen38` container, on **port 8000**, with `--gpu-memory-utilization 0.80`.
It holds **93.4 GiB**, leaving 16 GiB of 121 GiB available. Its restart policy is
`always`, so it survives a reboot. `ollama.service` is also enabled and
listening on 11434, currently with no model resident.

Two consequences, and the first is worse than the second.

**1. The capability probe checks that a port answers, not what answers.**
`config._check_endpoint` opens a socket to `127.0.0.1:8000` and calls that a
local reasoner. Right now that port answers — with Qwen. Run today, the probe
reports `local_reasoner: available`, the profile resolves to `spark`,
`local-only` is reported available, and every local-only reasoning call is
routed to a **non-NVIDIA model**, silently. `model_calls.model` would record the
identifier the code intended, not the one that actually answered, so the
telemetry would agree with the mistake.

That is a hackathon rules violation — no third-party models in the runtime path
— reached without anyone doing anything wrong. **The probe must verify served
model identity, not port liveness**, before anything is allowed to route to a
local reasoner. This is a defect in the shipped `compute-profiles` capability and
needs its own change.

**2. There is not enough memory for Spike B.** Lightning NVFP4 needs roughly
15-17 GiB resident and 16 GiB is available. The spike would OOM, or fit with
nothing to spare and no room for ASR or the embedder. Either stop the Qwen
container for the duration, or lower its `--gpu-memory-utilization` and restart
it. Decide before day 4 rather than discovering it at the prompt.

**Memory note:** a MoE model holds *all* 30B parameters resident. "3B active" is
a compute figure, not a memory one. NVFP4 is the default deployment target for
exactly this reason.

**The freed day is banked as slack.** A week-one plan with zero slack fails on
first contact. If it survives to Wednesday unspent, pull the seed generator
forward — it unblocks the most downstream work.

---

## Day 5 — Mon 31 Aug — Spike E: Nebius round trip + judge-target resolution

Three deliverables, all small, all load-bearing:
1. One Token Factory completion with real token accounting written to
   `model_calls`.
2. One Serverless Job: dispatch → poll → retrieve an artifact.
3. **Resolve the judge deployment target.** Confirm whether Serverless
   Endpoints can host a Next.js + FastAPI application or whether a container/VM
   target is required. This is a submission-blocking assumption and it does not
   get to sit unexamined until week seven.

**Also on day 5 — score the week-1 eval baseline.** Generate and score the six
held-out prompts against the `brain_sha` the baseline run recorded, not against
HEAD. Pinning to the recorded SHA is the entire point of splitting the baseline,
and it is the one step that can silently go wrong and quietly weaken the
eight-week delta. *Not done on day 5: there was no baseline row to score against
until 2 Sep, and scoring still waits on a judge — `local-inference` and
`nebius-executor`, not this capability.*

**Pass gate** — both calls succeed with telemetry rows; the judge-hosting
question has a written answer in `docs/decisions/`; `eval_results` rows exist
for 6 prompts × 3 samples, linked to the `brain_sha` the baseline run pinned.
*The judge-hosting question is answered — `docs/decisions/0009`. The
`eval_results` rows do not exist; `eval_results` is empty.*

**Abort criteria** — if Serverless Jobs are unusable, the build stage runs local
and Nebius usage narrows to Token Factory. That still satisfies the rules but
weakens the Technological Implementation score. Knowing on day 5 leaves time to
redesign; knowing in week 6 does not.

---

## Day 6 — Tue 1 Sep — Spike F: Nemotron Speech on aarch64 + synthetic night generator

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

## Day 7 — Wed 2 Sep — Spike D + night scrubber v0 + write-up

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

**TTS.** Still not week one, but no longer a risk either — **the week-3 spike
was pulled forward and run on 2026-08-28, and it passed.** All five MagpieTTS
voices synthesize on GB10 at RTF ~0.44 in 1.85 GB, alongside the reasoner.

The premise was wrong in a useful direction: this was justified as sharing "the
dependency stack the ASR spike already installs," but the ASR spike had not run
and the Spark had no NeMo, no torch and no CUDA toolkit outside containers. The
full dependency cost was paid here, so **the ASR spike now inherits a working
NeMo 3.1.0 aarch64 environment** rather than the other way round.

See `scripts/spikes/spike-c-tts-magpie/FINDINGS.md`.

**The celestial layer.** Week 6, after the scrubber works. It is worth real time
— but only once, and only on a foundation that already renders.

---

## Week-one failure condition

If capture-from-phone → logged entry is not working end to end by end of day
Wed 2 Sep, **stop every spike and fix only that.** Local model serving, Nebius
integration, and the scrubber are all recoverable in week two. A memory history
that starts late is not recoverable at all.
