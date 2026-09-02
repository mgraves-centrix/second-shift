## Scale

**L3 — Epic.** Cross-system rather than long: it spans the provider layer, an
authenticated inbound route on the API, the machine's network exposure, the
hosting of a second instance, and the shape of the cloud `Reasoner`. It also
resolves an open risk recorded in an accepted ADR, and adding a new one. A
design doc accompanies it.

## Why

Every obligation deferred out of day 1 collects here, and one of them is
submission-blocking.

`Executor` exists with `InProcessExecutor` behind it — jobs run locally and
immediately, which is a stand-in, not a fan-out. ADR 0004 makes parallel variant
generation the argument for Nebius being real rather than decorative: five builds
at once is the thing the Spark cannot do, and the reason the artifact is better.
Nothing does it yet.

The telemetry half is further along than it looks and stops at exactly the wrong
place. `Recorder.ingest_external` is written and tested: it validates the
dispatching invocation, refuses a forged or unknown parent, resolves depth so
remote work joins the tree at full depth rather than as an opaque span, and takes
the recorder's lock so ingest serializes through the one writer. **The transport
that carries it from a job does not exist.** Until it does, a Nebius job is work
the system paid for and cannot account for — and `model_calls` is where both the
cost curve and the local-versus-cloud chart are read from.

Pricing is no longer among the gaps. Lightning, Super and Ultra were read from the
Token Factory console on 27 Aug, standard and Batch, and are in
`config/pricing.toml`. A missing rate still fails loudly; none is missing.

## What Changes

**An `Executor` against Nebius Serverless Jobs.** `dispatch` submits one job per
build variant and returns a handle; `await_result` polls it to completion.
`JobResult` continues to carry the work product only — telemetry travels its own
channel, which is what keeps this interface independent of any serialization
format (ADR 0004).

**An authenticated telemetry ingest route** on the orchestrator's API, accepting
what `ingest_external` already validates and holding the recorder's lock rather
than opening a second connection to the database.

**A cloud `Reasoner`** for the Token Factory turns ADR 0004 assigns to it —
research synthesis, architect, critic — under `cloud-assisted` only. The airlock
already refuses it under `local-only` at the call and at the database.

**An ADR for the judge deployment target**, resolving the open risk ADR 0004
recorded rather than leaving it in a bullet.

Not in this change: the night pipeline that would call it, retrieval, or
redaction. Each has its own capability.

## Capabilities

### New Capabilities
- `nebius-executor`: out-of-process work on Nebius, and the authenticated
  channel that brings its telemetry back into the tree.

## Constitution Compliance

| Principle | Status | Note |
|---|---|---|
| 1. Brain plaintext under git | **Constrains** | The brain never leaves. A job receives assembled, policy-filtered context and never the memory that produced it. |
| 2. Privacy Airlock | **Constrains, and is the sharpest risk here** | This change introduces the system's first real egress. `local-only` work must never reach `token-factory` or `nebius-job`; `assert_permitted` refuses at the call and the `model_calls` CHECK makes it unrecordable. Retrieval stays local on every profile. Neither guard is weakened, made conditional, or bypassed — and the ingest route is inbound, so it carries no idea content outward. |
| 3. No empty mornings | **Constrains** | A job that fails or never returns must leave the stages before it committed. The executor therefore returns a failed `JobResult` rather than aborting a run, and a poll that exceeds its deadline is a recorded failure rather than an exception that unwinds the night. |
| 4. Text-first | Not applicable | No voice surface. |
| 5. One codebase, two deployments | **Implements** | The judge instance is this code on the `cloud` profile, with zero real data and labeled in-UI. Nebius specifics stay inside `providers/`; the night pipeline sees `Executor`. |
| 6. Scope boundary | Compliant | Nothing in `NOT_BUILDING.md`. Generated builds are produced, never run unsupervised — a Job produces artifacts, and nothing executes what it wrote. |
| 7. Telemetry from line one | **Implements** | This is the change that makes remote work accountable. A dispatched job that reports nothing is a hole in the cost curve, and `is_synthetic` continues to keep the judge instance's data out of every measurement. |

No violations. Principle 2 is the one to re-check at every implementation step:
it is the easiest to erode by convenience once a remote provider exists at all.

## Questions that blocked this change

These were decisions, not gaps in the writing, and each was asked where it
blocked. All three resolved on 2 Sep through `/openspec:clarify`. The reasoning
that made each a question is kept above its answer rather than replaced by it.

**The judge deployment target.** ADR 0004 recorded it as an open risk — whether
Nebius Serverless Endpoints can host a web application rather than only serving
models — and the day-5 spike that was to answer it has not run. It is
submission-blocking: without a hosting target there is no judge instance to
demonstrate. The pricing extract of 27 Aug supplies a real candidate that did not
exist when the risk was written: dedicated endpoints bill by GPU hour (H100
$4.05, L40S $2.00), which is rentable for a demo window rather than requiring a
serverless application target at all.

**Resolved: a Serverless AI Endpoint, on a no-GPU container VM.** An earlier
version of this answer argued Endpoints only serve models and reached for a
plain container or VM target instead. That premise was wrong. Endpoints and
Jobs both run an arbitrary container on a Compute container VM, and both
creation flows offer the identical choice — "Select whether the VM should have
GPUs" — with a VM lacking one a supported configuration, not a hypothetical
one. ADR 0004's open risk closes as answered, not deferred to the fallback it
named: Endpoints can host the application after all.

The cost argument survives and sharpens. Compute bills a non-GPU VM at $0.012
per vCPU-hour and $0.0032 per GiB-hour. A `2vcpu-8gb` preset run continuously —
730 hours, a full month — costs `2 × $0.012 × 730 + 8 × $0.0032 × 730 ≈ $36`.
The same month on an H100 dedicated endpoint, run the same way, is
`730 × $4.05 ≈ $2,957` — GPU rates for a process with no GPU work in it, made
concrete rather than asserted.

The two questions the marker ran together stay separated: the app runs on this
endpoint, and the models it calls are Token Factory per-token — hosting the
process on a Nebius Endpoint does not route its model calls through that
endpoint. The demo-window GPU rental is rejected as the default and kept only
as a latency contingency for a known demo slot — judges arrive unpredictably
across a multi-day window, and an hourly endpoint bills for the idle between
them.

One constraint the corrected answer carries that the first draft did not: a
no-GPU VM supports only the regular VM type, never preemptible — Nebius
reserves preemptible pricing for GPU platforms. That changes nothing here; a
judge instance cannot tolerate being preempted mid-demo regardless of what the
first draft assumed.

Recorded as a superseding ADR rather than by editing 0004.

**How a job reaches the machine that holds the brain.** Ingest is inbound: a
Nebius job must reach the orchestrator. Joining the job to the tailnet is the
intended route and keeps the endpoint off the public internet. A public endpoint
is simpler and widens the attack surface on the one machine holding every
captured idea and the brain. This is a security decision about the machine, not
an implementation detail, and the roadmap already says it needs deciding before
it is built.

**Resolved: neither. The job reports nothing and the orchestrator collects.**
The third option this design records is taken, and it dissolves the question
rather than answering it. With no inbound path there is no endpoint to secure,
and no credential to place inside an ephemeral job whose environment is visible
in the Nebius console.

`Executor.dispatch` / `await_result` is already submit-then-poll, so the poller
exists. The job writes telemetry to its own output; `await_result` collects it
and calls `ingest_external` locally, holding the recorder's lock — which was
already settled. The attack surface of the machine holding the brain and every
captured idea is unchanged by this capability, which is what Principle 2 asks of
it.

The cost is that a job's telemetry lands at completion rather than during the
run. Nothing watches a 2am fan-out live.

**Reporting telemetry twice.** A job that reports, is retried, and reports again
must not double-count. `ingest_external` has no idempotency key today: it
validates the parent and writes. Duplicated rows inflate exactly the numbers the
submission rests on, and silently.

**Resolved: a client-generated key per row, enforced by the recorder.** The job
generates its local ids once, when it records the work rather than when it
reports it, so a retry reports the same ids. `ingest_external` already takes
those local ids and returns the mapping to recorded ids; a
`UNIQUE (dispatching_invocation_id, local_id)` constraint makes a second report
a conflict, and the conflict returns the id already recorded instead of
inserting.

This is the path `capture` already uses: `entries.id` is a client-generated ULID
as primary key, and replay returns what is stored.

Keying on the job's own id was rejected because one job reports many invocations
and model calls, so it would dedupe whole reports or nothing. At-most-once with
retries dropped was rejected because a dropped report is a night whose costs are
under-counted silently, and cost per accepted artifact is a scored measurement.

The recorder enforces this rather than trusting the caller, for the reason
`UnknownDispatcher` exists: nothing about a report that arrived over the wire is
taken on faith.

## Decisions taken without a marker

- **`JobResult` still carries no telemetry.** ADR 0004 settled it and nothing
  here reopens it: telemetry over its own channel is what keeps the executor
  interface independent of a serialization format.
- **Ingest holds the recorder's lock.** `ingest_external` already does. A second
  connection would be a second writer against a database whose whole concurrency
  model is that there is one.
- **A failed job is a result, not an exception.** "No empty mornings" means a
  build variant that fails leaves the stages before it committed, so the executor
  reports failure rather than unwinding the run.
- **Pricing is settled and is not re-derived here.** The rates are in
  `config/pricing.toml` with their effective dates; a missing rate fails loudly.

## Impact

**New:** `secondshift/providers/nebius.py`; an ingest route on the API; an ADR
for the judge deployment target.

**Changed:** the registry binds them on the `cloud` profile, which today still
carries placeholders.

**Blocked on credentials.** No Nebius credential is present in the environment
this proposal was written in, so nothing here is implemented and nothing is
stubbed. A stub executor that returned plausible job results would be
indistinguishable in the data from a real fan-out, which is the one thing the
Nebius argument cannot afford.

**Risk:** this is the system's first real egress, and the privacy guarantee is the
product's claim rather than a feature of it. Every implementation step is checked
against principle 2 again, not once at the start.
