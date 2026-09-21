# Design — the API layer

## Context

Nine routes, one file, three sessions in five days each adding one route to it.
The refactor itself is not interesting; what it has to settle first is.

Two questions have been parked in `docs/prompts/API_LAYER.md` since the prompt
was written, and both were framed around a route that, it turns out, is not
being built. Getting that straight is most of this document.

## Decision 1 — authentication

### What the prompt assumed

> That changes the moment `nebius-executor` adds an inbound ingest route, which
> is the first path where something *not on the machine* talks to it.

### What is actually recorded

`openspec/changes/2026-09-02-add-nebius-executor/design.md` lays out three
shapes for how a Nebius job reaches the machine that holds the brain:

1. **The job joins the tailnet.** Ingest binds the tailnet interface only. Costs
   a tailnet auth key inside a container whose environment is visible in the
   Nebius console, and ephemeral nodes to clean up.
2. **A public authenticated endpoint.** Simplest to build. Puts a listening
   service holding every captured idea on the public internet behind one bearer
   token.
3. **The job reports nothing and the orchestrator reads.** The job writes
   telemetry beside its artifacts; `await_result`, which already polls, collects
   it and calls `ingest_external` locally under the recorder's lock.

The proposal records the resolution: **"Resolved: neither. The job reports
nothing and the orchestrator collects."** Option 3. No inbound path exists, so
there is no endpoint to secure and no credential to place inside an ephemeral
job.

**There is therefore no external consumer of this API, now or in the designed
future.** The premise both parked questions rested on is gone.

> **Drift found while grounding this.** That same proposal's deliverables list
> still says "**An authenticated telemetry ingest route** on the orchestrator's
> API." Its own decisions section, ninety lines below, resolves against building
> one. The deliverables line was written before the design argued the third
> option and was never brought back into line. `tasks.md` has no ingest-route
> task, and the spec's requirement is written transport-neutrally — "the channel
> carrying telemetry ... SHALL authenticate every report" — so nothing
> downstream inherited the error. One stale line, corrected in this change,
> which is also the line that put a question into `API_LAYER.md` that did not
> need to be there.

### The surface, then

- **ADR 0012**: the always-on machine owns a single origin and serves the API and
  the exported PWA together. A development machine serves `127.0.0.1` only.
- **ADR 0012** again: a second origin is a defect, not a convenience.
- `NOT_BUILDING.md` excludes accounts and multi-user.
- Reachability is `tailscale serve`, not the public internet.

Every consumer is same-origin, on one machine, for one person.

### The alternatives

**Per-route authentication in this layer.** A dependency, a configured secret,
and a decision at every route about whether it applies. Built today it would
guard nothing, and a guard nothing exercises is a guard nobody knows is broken.
Worse: authentication implies a principal, a principal implies an identity, and
`NOT_BUILDING.md` excludes accounts by name. Building the mechanism is a step
toward a thing the constitution's scope boundary excludes, taken speculatively.

**Authentication as one capability's concern.** If a future change reinstates an
inbound path, that capability's router carries its own guard.
`APIRouter(dependencies=[...])` applies a dependency to every route in a module
and to no route outside it, so the guard's blast radius is exactly the
capability that needs it. The cost of arriving there is one file — the same
measure this refactor is judged by.

**Neither, and no structure for it.** What exists today. Adding a guarded route
later would mean either guarding it inline in a 600-line file or introducing the
routers then, under deadline, next to the feature that needs them.

### Decision

**Authentication is a capability-owned concern. This layer builds none, and the
router split is what makes that affordable.**

What each costs when the question reopens:

| If the resolution holds (no inbound path) | If it reverses (an inbound route returns) |
|---|---|
| Per-route auth in this layer: dead code guarding nothing, plus a principal concept the scope boundary excludes. | Per-route auth in this layer: ready, but every route has been carrying a decision it never needed, and the mechanism has aged untested for however long. |
| Capability-owned: nothing built, nothing to maintain. | Capability-owned: one module gains `APIRouter(dependencies=[verify])` and one test. The other four modules do not change, and no route outside that capability can accidentally be exempted, because none was ever enrolled. |

The asymmetry is the argument. Capability-owned costs nothing in the likely case
and one file in the unlikely one.

## Decision 2 — versioning

The prompt asks this be decided on two facts rather than convention.

**Fact one:** the only consumer is a PWA built from `apps/web` and served by
this same process from `WEB_EXPORT`. It is not merely shipped from the same
repository — it is shipped *by the same process*, from a directory this module
resolves at import. It cannot skew from the API, because there is no deploy in
which one moves without the other.

**Fact two:** the ingest route would have had an external consumer. It is not
being built. The fact is void.

One fact survives and it argues against `/v1`. A version in the path exists to
let a producer change while a consumer it does not control keeps working. There
is no such consumer. `/v1` here would be a prefix maintained for an audience of
zero, and — worse — a lie in the URL, implying a compatibility promise nothing
is holding anybody to.

**Decision: no versioning.** The trigger for revisiting it is written into the
spec: the day a consumer exists that is not deployed with this API, the
capability introducing it prefixes its own router. That is one file, and it does
not require the other four to be re-labeled, because they still have no external
consumer to version for.

## Decision 3 — the module boundary

The success measure is "adding a route means adding or touching one file", with
"a new contributor can find where a route lives from its path alone" second.

**By path segment.** `/health`, `/capabilities`, `/entries`, `/runs`, `/events`,
`/morning`, `/decisions`, `/artifacts` — eight modules for nine routes, two of
them holding one function each, and `/runs/{id}/timeline` separated from
`/events/{id}` although neither means anything without the other. Maximum
discoverability, and a package that is mostly ceremony.

**By capability.** Five modules. `night.py` holds `/runs`, the timeline and
`/events/{id}`, which the existing module docstring already groups as "read back
what a night wrote". `morning.py` holds the briefing and its answer route.

**By verb, or by read/write.** Rejected without much argument: it puts
`POST /entries` beside `POST /decisions/{id}/answer`, which share an HTTP method
and nothing else. A contributor looking for capture would have to know the
method before they could find the file.

**Decision: by capability**, accepting that two of nine routes are not findable
from their first path segment. Both are the second noun of a capability that
already owns a module, and both are stated in the routes package docstring. The
alternative buys strict path-to-file mapping with two single-function modules
and a split between a timeline and the event detail it drills into.

## Decision 4 — how a router reaches the context

Today `get_context` is a closure inside `create_app`, returning the argument.
A module-scope router cannot close over a value that does not exist until
`create_app` runs.

**A module global set by `create_app`.** Import-order dependent, untestable in
parallel, and two apps in one process share one context. Rejected.

**A factory per route module** — `def router(context) -> APIRouter` called by
`create_app`. Keeps the closure, works, and costs a function call per module.
But every router becomes a function that must be *called*, so a module cannot be
imported and inspected without building one, and the natural `APIRouter`
decorator idiom is lost inside a nested scope. It also does not remove the
closure problem, it relocates it.

**`app.state` plus a request-scoped dependency.** `create_app` sets
`app.state.context = context`; `get_context(request)` returns
`request.app.state.context`. Module scope, no globals, and two apps in one
process are independent. It is the idiom FastAPI documents for exactly this.

**Decision: `app.state` with a request-scoped dependency.** `create_app(context)`
and `Context` keep their signatures, which is what the 74 test functions
actually depend on — none overrides `get_context`, so the closure's identity is
not part of the contract.

## What is deliberately not done

- No auth framework. Decided above; built when a route needs it.
- No `/v1`. Decided above.
- No new response envelope. Wrapping payloads in `{data: ...}` breaks a working
  PWA for no benefit.
- No new route. This moves what exists.
- No change to `schemas.py`. Its deliberate absences are airlock enforcement
  expressed as a type, and the safest way to preserve them is not to open the
  file.
- No rate limiting, no CORS. Same origin by construction (ADR 0012).
