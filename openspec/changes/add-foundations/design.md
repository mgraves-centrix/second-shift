## Context

The architecture is already settled in `docs/ARCHITECTURE.md` and ADRs 0001–0007.
This document covers only what those do not: the mechanism by which telemetry
context propagates, the provider interface signatures, and how profile
resolution decides what it decides.

Constraints that shape the approach:

- SQLite, single writer, WAL mode. The orchestrator, the API and the night
  state machine all write. Concurrency is low but non-zero.
- Agents call agents. The invocation tree must be captured without every
  function taking a `parent_invocation_id` parameter.
- Some work runs out of process — Nebius Serverless Jobs execute the build
  stage remotely. Their telemetry has to rejoin the tree.
- Nothing here may depend on a model backend. Days 4–6 spikes could each fail;
  this foundation must survive that.

## Goals / Non-Goals

**Goals:**
- Telemetry that is impossible to forget to write, because the recorder owns the
  invocation lifecycle rather than being called alongside it.
- Provider interfaces narrow enough that a spike can implement one in an hour,
  and stable enough not to churn once three backends exist.
- Profile resolution that is deterministic, inspectable, and honest about
  reduced capability.
- Append-only discipline enforced by the data-access layer.

**Non-Goals:**
- Any concrete provider backend beyond a null implementation for tests.
- Retrieval, embedding storage, or the brain repository.
- HTTP routes. Day 2.
- Performance work. At this scale correctness dominates; the night writes
  hundreds of rows, not millions.

## Decisions

### Telemetry context propagates through `contextvars`, not parameters

An `InvocationContext` is held in a `contextvar`. Opening an invocation pushes a
new context whose parent is whatever is currently set; closing it restores the
previous one. A context manager owns both ends, so an invocation cannot be left
open by an early return or an exception.

`model_calls` and `tool_calls` read the current invocation from the contextvar
at write time. A provider therefore records its own telemetry without being
handed an id, which is what makes instrumentation hard to skip.

*Alternative rejected:* threading `parent_invocation_id` through every call
signature. Explicit, but every new code path is an opportunity to forget, and
the constitution's Telemetry From Line One principle is exactly the thing that
erodes incrementally.

*Alternative rejected:* OpenTelemetry. The right answer for a system with
distributed tracing needs; here it adds a dependency and an export pipeline to
solve a problem that is four tables and a contextvar.

`contextvars` propagate correctly into `asyncio` tasks. They do **not** propagate
into threads created by `ThreadPoolExecutor`, so any threaded work must capture
and re-attach the context explicitly. This is a documented sharp edge with a
helper, not something left to memory.

### Providers are four narrow interfaces plus a registry

```
Transcriber.transcribe(audio) -> Transcript
Reasoner.complete(messages, *, policy, effort) -> Completion
Embedder.embed(texts) -> list[Vector]
Executor.dispatch(job) -> JobHandle ; Executor.await_result(handle) -> JobResult
```

Every method is instrumented by the base class, not by each implementation.
Implementations override a `_do_*` method; the public method owns the telemetry
write, the policy assertion and the failure classification. An implementation
that forgets to record telemetry is not possible, because it never writes any.

`Reasoner.complete` takes `policy` explicitly rather than reading it from
context. The Airlock is the one place where an implicit value would be
dangerous, so it is passed and asserted at every call.

### Profile resolution is a probe with a recorded result

Resolution order: `SECOND_SHIFT_PROFILE` environment variable, else a capability
probe, else `cloud`. The resolved profile and the probe's findings are written
once at startup and stamped onto every `run` and `model_call`, so any row can be
explained after the fact.

The probe checks for CUDA availability, a reachable vLLM endpoint, and NeMo
importability — independently, reporting a capability set rather than a single
boolean, so a partial stack is visible rather than collapsing to a yes/no.

### Append-only is enforced in the repository layer

The repository exposes `insert_*` and a small set of named completion methods
(`close_invocation`, `answer_decision`, `resolve_failure`). There is no generic
`update`. Anything that looks like a counter is a view. This is the difference
between a documented convention and one that holds.

### Migrations are numbered SQL, forward-only

`db/migrations/NNNN_name.sql` applied in order against a `schema_version` table.
No ORM, no migration framework, no down-migrations. At this scale and duration a
migration tool is more moving parts than the thing it manages, and rollback is
`git checkout` plus a fresh database during the pre-dogfooding window.

## Risks / Trade-offs

**Interfaces designed before any real backend exists.** Days 4–6 will teach us
things about vLLM, NeMo and Serverless Jobs that this design cannot anticipate.
Mitigated by keeping the interfaces narrow — four methods total — so a change is
cheap. Accepted deliberately: the alternative is no telemetry until day 6.

**`contextvars` are invisible.** Context that propagates automatically is
context that can be wrong in ways nothing points at. Mitigated by a test that
asserts tree shape — depth, parentage, ordering — rather than merely that rows
exist.

**Out-of-process telemetry is unsolved here.** Serverless Jobs run remotely and
must rejoin the invocation tree.

[NEEDS CLARIFICATION: How does a Nebius Serverless Job report its telemetry back into the invocation tree? Options: the job returns a structured telemetry blob in its result which the orchestrator replays into the recorder; the job writes directly to a shared endpoint; or job-internal work is recorded as one opaque invocation with no children. The first preserves the tree and keeps SQLite single-writer, but requires a stable serialization format decided before the Executor interface is frozen.]

**Single-writer SQLite.** WAL mode plus one process is fine. If the night state
machine and the API ever write concurrently under load, this becomes a
serialization point. Not a day-1 problem, but the repository layer should not
assume it will never matter.
