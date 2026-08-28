# 0008 — Telemetry propagates through context; quarantine is derived

**Status:** accepted · **Date:** 2026-08-27

## Context

Two decisions were made while implementing `add-foundations` that constrain
every later change. Both were argued in that change's `design.md`, which now
lives in `openspec/changes/archive/`. They are recorded here because
`docs/decisions/` is where a future reader looks, and a decision nobody can find
gets re-litigated or violated by accident.

## Decision 1 — Telemetry propagates through `contextvars`

An `InvocationContext` lives in a `contextvar`. Opening an invocation pushes a
new context whose parent is whatever is current; a context manager owns both
ends, so an invocation cannot be left open by an early return or an exception.

`model_calls`, `tool_calls`, `events` and `failures` read the current invocation
at write time. A provider therefore records its own telemetry without being
handed an id.

Provider base classes hold this: every public method is concrete and owns the
telemetry write; implementations override an internal `_do_*` method only. An
implementation that forgets to record telemetry is not possible, because it
never writes any.

**Alternative rejected:** threading `parent_invocation_id` through every call
signature. Explicit, but every new code path becomes an opportunity to forget,
and Telemetry From Line One is exactly the principle that erodes incrementally
rather than all at once.

**Alternative rejected:** OpenTelemetry. Correct for a system with distributed
tracing needs. Here it adds a dependency and an export pipeline to solve what is
four tables and a contextvar.

### The sharp edge

`contextvars` propagate into `asyncio` tasks automatically. They do **not**
propagate into threads from `ThreadPoolExecutor` or `threading.Thread` — a
worker starts from an empty context and its telemetry is recorded as a root
invocation, silently detached from the tree.

`telemetry.context.propagate()` captures the calling context and re-attaches it
inside the worker. Any threaded work must use it. Tests assert the behavior in
both directions, so the trap is demonstrated rather than only described.

### Consequence

SQLite's `check_same_thread` guard is disabled on the connection. Threaded work
records its own telemetry and out-of-process telemetry ingests through the same
connection; serialization is the `Recorder`'s lock. **Anything that writes
outside `Recorder` must take that lock.**

## Decision 2 — Quarantine is derived, not stored

An entry whose policy the resolved profile cannot honor is never dispatched. That
state is computed from the current capability report at read time. It is not a
stored status on `entries`.

**Why:**

- **Release is automatic.** When the local reasoner returns, previously blocked
  entries are eligible again with no manual re-entry and no reconciliation job
  that could itself fail at 2am.
- **No stored flag can go stale against reality.** The blocked list is always the
  truth about right now, not the truth about whenever a writer last ran.
- It avoided a migration to widen the `entries.status` CHECK constraint, on day
  one, before any data existed to migrate.

**Alternative rejected:** a `quarantined` status written at screening time. It
reads more obviously, and it is what most systems do — but it requires a
release path, and a release path that fails leaves ideas stranded invisibly.
Derived state has no such failure mode.

**Trade-off accepted:** screening cost is paid per read rather than once per
write. At five to ten captures a day this is not measurable. If the queue ever
grows enough for it to matter, the fix is a cache keyed on the capability
report — not a stored flag.

## Consequences

- Any new agent, provider or stage inherits telemetry by construction. Adding
  one is not an occasion to remember anything.
- Quarantine questions are answered by asking the capability report, never by
  reading a column.
- Both decisions are load-bearing for constitution principles 2 and 7. Changing
  either needs an ADR that supersedes this one.
