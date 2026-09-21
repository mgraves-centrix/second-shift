# 0013 — The API has no authentication and no version

**Status:** accepted · **Date:** 2026-09-21

## Context

Splitting `api/app.py` into one module per capability meant deciding two things
the single file had never had to state: whether authentication is a concern of
the layer, and whether the paths carry a version.

Both questions had been parked in `docs/prompts/API_LAYER.md` since it was
written, and both were framed around the same future route — an inbound
telemetry ingest endpoint that a Nebius job would call. The prompt's words:
"that changes the moment `nebius-executor` adds an inbound ingest route, which
is the first path where something *not on the machine* talks to it."

That route is not being built. `nebius-executor`'s design argued three shapes
for how a job reaches the machine holding the brain — the job joins the tailnet,
a public authenticated endpoint, or the job reports nothing and the orchestrator
reads — and took the third. `Executor.dispatch` / `await_result` is already
submit-then-poll, so the job writes its telemetry beside its artifacts and the
poller calls `ingest_external` locally, under the recorder's lock. With no
inbound path there is nothing to authenticate and no credential to place inside
an ephemeral container whose environment is visible in a console.

The premise both questions rested on was therefore already gone, and had been
since 2 Sep. What kept it alive was one line in that proposal's deliverables
list still promising "an authenticated telemetry ingest route", ninety lines
above the section resolving against one. Corrected with this decision.

## Decision

**The API authenticates nothing, and no path carries a version.**

Authentication, if it ever becomes necessary, is **the concern of the capability
that needs it** — declared on that capability's own router, applying to its
routes and to no others. It is not a per-route concern this layer supports, and
no mechanism for it is built in advance.

Versioning, if it ever becomes necessary, is introduced the same way: by the
capability with the consumer that needs it, on its own routes.

## Consequences

- **Nothing guards nothing.** Every consumer today is same-origin, on one
  machine, for one person: ADR 0012 puts the API and the exported PWA on a
  single origin owned by the always-on machine, reachable over `tailscale serve`
  rather than the public internet, and `NOT_BUILDING.md` excludes accounts. A
  guard built now would protect a surface nothing can reach, and a guard nothing
  exercises is a guard nobody knows is broken.

- **It stays cheap to reverse.** `APIRouter(dependencies=[...])` applies a
  dependency to every route in a module and to none outside it. If an inbound
  path is ever reinstated, that capability's module gains one line and one test,
  and the other four modules do not change. The cost of being wrong here is one
  file, which is the same measure the route split is judged by.

- **No principal is introduced.** Authentication implies a principal, a
  principal implies an identity, and accounts are excluded by name. Building the
  mechanism speculatively would be a step toward a thing the scope boundary
  excludes, taken for a caller that does not exist.

- **`/v1` would be a promise to nobody.** A version in a path exists so a
  producer can change while a consumer it does not control keeps working. The
  only consumer is a PWA this same process serves from `WEB_EXPORT`; it is not
  merely shipped from the same repository, it cannot be deployed apart from the
  API at all. A prefix maintained for an audience of zero also implies a
  compatibility promise nothing holds anybody to.

- **Cost: the reversal is a design question, not a configuration one.** There is
  no switch. Reinstating an inbound path means re-arguing where the guard lives
  and what it checks, which is the right amount of friction for reopening a
  decision about the machine that holds every captured idea.

- **This does not weaken ADR 0012.** One origin is why there is nothing to
  authenticate. A second origin would reopen this decision, which is one more
  reason a second origin is a defect rather than a convenience.
