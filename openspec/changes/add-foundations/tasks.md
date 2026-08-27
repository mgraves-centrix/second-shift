## 1. Environment

- [ ] 1.1 Create `apps/api/pyproject.toml` for the `secondshift` package; Python 3.12+, `pytest` and `pytest-asyncio` as the only dependencies.
- [ ] 1.2 Create the venv with `python -m venv` and install with pinned constraints. Never `uv run` — on the Spark it re-resolves the environment to x86_64 and destroys it.
- [ ] 1.3 Create the package skeleton: `db/`, `telemetry/`, `providers/`, `airlock/`, plus `config.py`. Every subpackage gets an `__init__.py`.
- [ ] 1.4 Verify: `python -m pytest` runs and collects zero tests without error.

## 2. Persistence

Blocks groups 3–5. Nothing else can be built until the tables exist.

- [ ] 2.1 Move `db/schema.sql` to `db/migrations/0001_initial.sql` unchanged.
- [ ] 2.2 Write the migration runner: numbered files applied in order against a `schema_version` table, forward-only, no-op when current.
- [ ] 2.3 Write the connection factory: WAL mode, `foreign_keys = ON`, row factory returning typed rows.
- [ ] 2.4 Write the repository layer with insert methods and the closed set of named completion operations — `close_invocation`, `answer_decision`, `resolve_failure`. Expose no generic update or delete.
- [ ] 2.5 Test: fresh database applies all migrations; re-running applies none; a database at version N applies only N+1 onward.
- [ ] 2.6 Test: the repository exposes no method that mutates a recorded `model_calls` row.
- [ ] 2.7 Test: `failure_ledger` derives a recurrence count of 3 from three rows sharing a signature.

## 3. Telemetry

Depends on group 2. Groups 3 and 4 can proceed in parallel once persistence lands.

- [ ] 3.1 Implement `InvocationContext` held in a `contextvar`, carrying the current invocation id, run id and depth.
- [ ] 3.2 Implement the `invocation()` context manager: opens an `agent_invocations` row with the current context as parent, pushes a new context, and closes the row on exit including on exception.
- [ ] 3.3 Implement recorders for `model_calls`, `tool_calls`, `events` and `failures`, each reading the current invocation from context rather than taking it as a parameter.
- [ ] 3.4 Implement failure classification into the taxonomy, with a normalized signature for deduplication and a fallback that preserves the original message for unrecognized errors.
- [ ] 3.5 Implement the threaded-context helper that captures and re-attaches context across `ThreadPoolExecutor` boundaries, and document it as a sharp edge in the module docstring.
- [ ] 3.6 Implement cost computation from a git-tracked `pricing.yaml` keyed by provider and model with `effective_from` dates, applying the rate in effect at the call timestamp. A missing rate raises a typed failure; it never records zero.
- [ ] 3.7 Implement the externally-attributed telemetry path: the recorder accepts invocations and model calls naming an existing dispatching invocation, serialized through the orchestrator's single writer. Transport is out of scope here and lands with the Nebius executor.
- [ ] 3.8 Test: three nested invocations record depths 0, 1, 2 with correct parentage.
- [ ] 3.9 Test: three concurrent sibling invocations share a parent and none inherits another sibling's context.
- [ ] 3.10 Test: an invocation whose body raises is closed with `outcome = 'failed'` and writes a typed failure row.
- [ ] 3.11 Test: a known rate is applied at write time; a missing rate fails loudly; adding a later `effective_from` leaves recorded costs unchanged.
- [ ] 3.12 Test: telemetry attributed to five concurrent dispatchers attaches under the correct parent in each case, and an unknown dispatcher is rejected without writing orphans.
- [ ] 3.13 Test: events carry renderable scalar columns, verified by rendering a timeline without reading `payload_json`.

## 4. Provider interfaces

Depends on group 2. No concrete backend beyond the null implementation — real backends arrive with their spikes on days 4–6.

- [ ] 4.1 Define `Transcriber`, `Reasoner`, `Embedder` and `Executor` as abstract base classes. Each public method is concrete and owns telemetry; implementations override an internal `_do_*` method only.
- [ ] 4.2 `Reasoner.complete` takes `policy` as an explicit parameter, asserted at call time rather than read from context.
- [ ] 4.3 Implement null/echo providers for each interface, for testing and for a profile with no backend configured.
- [ ] 4.4 Implement the registry that binds interfaces to implementations by resolved profile.
- [ ] 4.5 `Executor.dispatch` takes a telemetry descriptor carrying the ingest destination, its credential, and the dispatching invocation id. `JobResult` carries the work product only and never telemetry records.
- [ ] 4.6 Test: dispatching from within an active invocation produces a descriptor naming that invocation, and a returned `JobResult` contains no telemetry payload.
- [ ] 4.7 Test: a new implementation overriding only its internal method produces `model_calls` rows without containing telemetry code.
- [ ] 4.8 Test: no provider SDK import and no hardcoded model identifier exists outside the providers package, asserted by a source scan over `agents/`, `night/` and `api/`.

## 5. Compute profile and airlock

Depends on groups 2 and 4.

- [ ] 5.1 Implement the capability probe reporting CUDA availability, local endpoint reachability and speech-stack importability as independent findings.
- [ ] 5.2 Implement profile resolution: `SECOND_SHIFT_PROFILE`, then probe, then `cloud`. Record the resolved profile and probe findings at startup.
- [ ] 5.3 Implement policy resolution producing `effective_policy` and `policy_source` for a run, refusing to widen an entry's default without an attributable decision.
- [ ] 5.4 Implement the capability report: it returns every policy with an availability flag and, where unavailable, the specific probe finding that caused it. Unavailable policies are returned marked, never omitted.
- [ ] 5.5 Implement quarantine: an entry whose policy the resolved profile cannot honor is never dispatched, no run is created for it, and it is retrievable as blocked with its cause. Entries whose policy the profile can honor continue to dispatch normally.
- [ ] 5.6 Implement quarantine release: when capability returns, previously quarantined entries become eligible again without manual re-entry.
- [ ] 5.7 Test: `SECOND_SHIFT_PROFILE=cloud` overrides a working local stack.
- [ ] 5.8 Test: profile resolves to `cloud` on a machine with no CUDA and no reachable endpoint.
- [ ] 5.9 Test: a partial local stack degrades to `cloud`, startup proceeds, and the causing findings are readable at runtime.
- [ ] 5.10 Test: a `local-only` entry on a degraded profile is quarantined with its cause, while a `cloud-assisted` entry on the same profile dispatches normally.
- [ ] 5.11 Test: a `local-only` entry resolves a run whose effective policy is not silently widened.

## 6. Day 1 pass gates

These are the gates recorded in `docs/WEEK_ONE.md`. All must pass before day 2 begins.

- [ ] 6.1 Gate: migrations apply clean against a fresh database.
- [ ] 6.2 Gate: a test writes a run with nested `agent_invocations` at depth 2 or greater, with `model_calls` attached, and reads the tree back in correct shape.
- [ ] 6.3 Gate: recording a `local-only` model call against a remote provider is rejected by the database constraint.
- [ ] 6.4 Gate: profile resolution returns `cloud` on a machine with no CUDA.
- [ ] 6.5 Gate: a `local-only` entry on a degraded profile is quarantined rather than dispatched, and the capability report names the finding.
- [ ] 6.6 Run the full suite and record the baseline timing in the failure ledger for later comparison.
- [ ] 6.7 Commit, and update `docs/WEEK_ONE.md` to mark day 1 complete with anything learned that changes later days.
