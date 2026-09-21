# Split the API into one module per capability

## Scale classification

**L2 — Feature.** One package, under a day, no schema change, no new route and
no behavior change. It carries a `design.md` anyway, because the design rule
fires on its own trigger: two decisions — whether authentication is this layer's
concern, and whether the API is versioned — need their alternatives argued
before a spec commits to either, and this is the change that has to answer them.

## Why

`apps/api/secondshift/api/app.py` is one file holding nine routes, the context
factory, four response mappers and the static mount. It was 368 lines when the
prompt for this work was written, 473 on 19 Sep and **539 today** — the growth
is the argument, not any one figure. Three sessions added a route to it in the
last five days (`morning-interview`, `morning-screen`, `judge-mode`), and each
had to read the whole file to add one function to it.

`docs/ARCHITECTURE.md:106` specifies `api/` as "app.py, schemas, endpoint
modules". The endpoint modules do not exist. That line has been describing a
tree nobody built since the architecture was written, which means every session
that read it for orientation was oriented at something imaginary.

The original case for running this early was scheduling: five later sessions
would each add routes and would collide in one file. **That case is largely
spent** — three of the five shipped in sequence and paid the cost. What is left
is the file's size, the documented-but-absent tree, and two capabilities
(`nebius-executor`, and whatever serves a live night) that still have routes to
add.

## What changes

**A `routes/` package, one module per capability**, each exporting an
`APIRouter`, with `create_app` reduced to building the app, including the
routers, and mounting the PWA last.

| Module | Routes |
|---|---|
| `routes/system.py` | `GET /health`, `GET /capabilities` |
| `routes/capture.py` | `POST /entries` |
| `routes/night.py` | `GET /runs`, `GET /runs/{run_id}/timeline`, `GET /events/{event_id}` |
| `routes/morning.py` | `GET /morning`, `POST /decisions/{decision_id}/answer` |
| `routes/artifacts.py` | `GET /artifacts/{artifact_id}` |

The rule is one module per capability, and the path's first segment names it in
seven of nine cases. The two exceptions are `/events/{id}`, which exists to
drill into a timeline and is meaningless apart from one, and
`/decisions/{id}/answer`, which is the morning interview's write side. Both are
second nouns owned by a capability that already has a module. A rule with two
stated exceptions is more honest than a rule that would put four files where two
belong.

**`context.py`** takes `Context`, `build_context` and a module-level
`get_context`. The current `get_context` is a closure over `create_app`'s
argument, which a module-scope router cannot see; the context moves to
`app.state` and the dependency reads it from the request. `app.py` re-exports
`Context` and `build_context` so that `from secondshift.api.app import Context,
create_app` keeps working — that import appears in three test files and is what
**74 test functions** rest on.

**`mappers.py`** takes the four row-to-response translations. `capability_payload`
has two callers in different route modules and cannot live in either without a
route module importing another route module. Putting the other three beside it
costs a second import in two files and buys the rule "a route module holds
routes" with no exception to remember.

**A guard that the static mount is last.** `create_app` raises if anything was
registered after it, and a test asserts `GET /runs` answers JSON rather than the
PWA's HTML — the failure this ordering exists to prevent, which is otherwise
silent.

**Characterization tests** capture every current response against a seeded
database and assert byte equality after the move.

## The two decisions

Argued in `design.md`; stated here because they are the reason this needs a
proposal rather than a task list.

**Authentication: not this layer's concern, and not per-route.** The prompt
framed it as "this changes the moment `nebius-executor` adds an inbound ingest
route." It does not: `nebius-executor`'s design already resolved that question
and **took the option with no inbound route at all** — the job writes telemetry
beside its artifacts and `await_result`, which already polls, collects it and
calls `ingest_external` locally. With no inbound path there is nothing to
authenticate. Combined with ADR 0012 (one origin, on the always-on machine,
serving API and PWA together) and `NOT_BUILDING.md` excluding accounts, every
consumer of this API is same-origin and local. This layer builds no
authentication. What it does is make authentication **cheap to add to one
capability later**: `APIRouter(dependencies=[...])` scopes a guard to one
module, so if that resolution ever reverses, the cost is one file — which is
this refactor's whole success measure, arriving for free.

**Versioning: no `/v1`.** The only argument for it was an external consumer, and
that consumer was the ingest route that is not being built. The consumer that
exists is a PWA shipped from this repository in the same deploy; it cannot skew
from the API because it cannot be deployed apart from it. The day something
outside this deploy consumes the API, the capability that introduces it prefixes
its own router — again one file.

## Impact

**Affected specs:** `api-layer` (new).

**Affected code:** `apps/api/secondshift/api/` — `app.py` shrinks to `create_app`
and the mount; `context.py`, `mappers.py` and `routes/` are new. `main.py`,
`schemas.py`, `titles.py` and `location.py` are untouched.

**No test is modified.** If one had to be, the contract changed and this stopped
being a refactor.

## Constitution Compliance

| Principle | Bearing | How this change stands |
|---|---|---|
| 1. Brain plaintext under git | Not engaged | No brain read or write moves. |
| 2. The Privacy Airlock | **Constrains** | `schemas.py` is not touched, so the deliberate absences stay exactly as written — `TimelineEventResponse` has no payload field and `EventDetailResponse` has no field prompt or completion text could travel in. No response envelope, no generic passthrough, no new serializer: the airlock here is expressed as the absence of a field, and only a "tidy-up" of `schemas.py` could break it. `/artifacts/{id}` keeps its id-addressing and its root containment check. |
| 3. No empty mornings | Not engaged | `GET /morning` is moved verbatim; it still assembles from rows with no model call. The characterization test proves the response is byte-identical. |
| 4. Text-first, voice layered | Not engaged | No surface change. |
| 5. One codebase, two deployments | **Constrains** | No module branches on which instance is running. Routers are included unconditionally; the judge instance still differs by profile and seeded data only. The one conditional in `create_app` is `WEB_EXPORT.is_dir()`, which is build state rather than deployment identity, and it predates this change. |
| 6. Scope boundary | **Constrains** | No new route. `POST /decisions/{id}/answer` keeps the decision id in the path, which is how "no general chat interface" is enforced by URL shape rather than by a rule somebody remembers. Splitting the file must not soften that: the route moves with its docstring. |
| 7. Telemetry from line one | **Constrains** | Every write still goes through `ctx.recorder`. A route module opening its own connection or writing rows directly would be a second writer; none does, and the capture route's two `record_event` calls move unchanged. |

No violation. Nothing here is blocking.

## Risk

**The characterization test compares nothing.** A byte-equality test written
against responses captured from the same code it is testing passes trivially if
the capture is wrong. Mitigated by proving it can fail — rename one response
field and watch it go red — before moving a line.

**The mount ordering regresses silently.** Guarded at construction and in a
test, because the symptom is the PWA answering an API call with HTML, which
looks like a frontend bug for as long as it takes to find.

**`get_context` changes shape.** From a closure to a request-scoped dependency.
No test overrides it today, so nothing depends on the closure's identity; the
observable contract is `create_app(context)`, which does not move.
