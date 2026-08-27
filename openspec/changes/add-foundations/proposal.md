## Why

Day 1 of a 64-day build. Nothing exists yet except documentation and a schema
file that has never been applied by application code.

Two constraints make this the first change rather than one of several:

**Telemetry cannot be retrofitted.** The submission rests on an eight-week trend
— eval scores rising, cost per accepted artifact falling, local-vs-cloud token
ratio proving the Privacy Airlock. A gap in that data is unrecoverable, and it
would land exactly where the trend needs continuity. Every agent invocation and
model call must be logged from the first run, including during development.

**Dogfooding starts on day 3.** The capture path has to work end to end before
week two, because the week-1-versus-week-8 brain diff is the centerpiece and
that clock cannot be started retroactively. Day 2 builds the capture API on top
of whatever exists after day 1, so the persistence and telemetry layers must be
finished and correct before then.

This change establishes the four foundations every later change depends on. It
deliberately ships no user-visible behavior.

## What Changes

- **Persistence.** Apply `apps/api/secondshift/db/schema.sql` from application
  code, with a forward-only migration runner and a `schema_version` table.
  Repository layer with typed accessors. Append-only discipline enforced in the
  data-access layer, not merely documented.
- **Telemetry.** A recorder that opens and closes `agent_invocations`, and
  writes `model_calls`, `tool_calls`, `events` and `failures`. Invocation
  parentage propagates through `contextvars`, so the agent tree is captured
  without threading an id through every function signature.
- **Provider interfaces.** `Transcriber`, `Reasoner`, `Embedder`, `Executor` as
  abstract interfaces plus a registry. No concrete backend implementations in
  this change beyond a null/echo provider used for testing — those arrive with
  their spikes on days 4–6.
- **Compute profile resolution.** `SECOND_SHIFT_PROFILE`, else a boot-time
  capability probe, else `cloud`. The profile determines which provider
  implementations the registry binds and whether `local-only` policy is
  available at all.

Not in this change: FastAPI routes, the PWA, any real model backend, the brain
repository integration, retrieval.

## Capabilities

### New Capabilities
- `persistence`: schema application, forward-only migrations, append-only
  data-access discipline, and the synthetic-data flag that keeps development
  and seed rows out of every measurement.
- `telemetry`: recording agent invocations as a tree, and the model calls, tool
  calls, events and typed failures attached to them.
- `compute-profiles`: profile resolution, capability probing, and the provider
  interfaces that make the Spark a capability tier rather than a requirement.
- `privacy-airlock`: policy resolution per run, and enforcement that a
  `local-only` idea can never reach a remote provider.

### Modified Capabilities
None — this is the first change in the project.

## Constitution Compliance

Checked against all seven principles in `openspec/constitution.md`.

| Principle | Status | Note |
|---|---|---|
| 1. Brain Is Plaintext Under Git | Compliant | No memory store introduced. Brain integration is a later change and remains a sibling repository. |
| 2. The Privacy Airlock | **Implements** | The `CHECK` constraint and policy resolution are delivered here. |
| 3. No Empty Mornings | Compliant | `run_stages` ships as an independent table so stages can commit separately. |
| 4. Text-First, Voice Layered On | Compliant | No voice surface in scope; `Transcriber` is an interface with no concrete backend. |
| 5. One Codebase, Two Deployments | **Implements** | Provider interfaces and profile resolution are this principle. |
| 6. Scope Boundary | Compliant | Nothing from `NOT_BUILDING.md`. |
| 7. Telemetry From Line One | **Implements** | This change is the instrumentation. |

No violations found. Three principles are implemented rather than merely
respected, which is the point of sequencing this first.

## Impact

**New code:** `apps/api/secondshift/` — `db/`, `telemetry/`, `providers/`,
`airlock/`, `config.py`.

**Dependencies:** Python standard library plus `pytest`. No model, network or
provider SDK dependency is introduced — those land with their spikes, so a
failure on days 4–6 cannot invalidate this foundation.

**Downstream:** every subsequent change. The capture API (day 2) writes
`entries` through this repository layer; the night state machine records through
this recorder; each provider spike implements one of these interfaces.

**Risk if wrong:** an interface mistake here is expensive after day 3, because
dogfooding means real data is accumulating against the schema. Getting the
append-only and `is_synthetic` discipline right matters more than getting it
quickly.

**Environment:** `python -m venv` and `pip` with pinned constraints. `uv run` is
never used — on the Spark it re-resolves the environment to x86_64 and destroys
it.

## Open Questions

[NEEDS CLARIFICATION: On the `cloud` profile, `local-only` policy cannot be honored. At capture time, should the local-only option be hidden entirely, or shown disabled with an explanation of why it is unavailable? Shown-disabled teaches the privacy model and makes the guarantee legible; hidden is less confusing but silently narrows what the user knows the product can do.]

[NEEDS CLARIFICATION: What is the source of truth for `model_calls.estimated_cost_usd`? Token Factory per-token pricing has not been verified, and the cost-per-accepted-artifact curve is a scored artifact — so a hardcoded guess is not acceptable. Options: a checked-in `pricing.yaml` updated by hand, or a startup fetch with a cached fallback.]

[NEEDS CLARIFICATION: When the capability probe finds a partial local stack — CUDA present but the vLLM endpoint unreachable, say — should profile resolution fall back to `cloud`, or fail loudly? Silent fallback would run a `local-only` idea into a profile that cannot accept it, which the Airlock would then reject at the database. Failing loudly is safer but blocks startup on a transient condition.]
