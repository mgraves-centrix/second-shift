## Context

ADR 0004 settled *what* runs on Nebius. This settles *how* the two channels
between the machine and Nebius work: work going out, and telemetry coming back.

The asymmetry is the whole design problem. Dispatch is outbound to a documented
API from a machine that already makes outbound calls. Ingest is **inbound to the
one machine that holds every captured idea and the brain**, from a process on
someone else's infrastructure. They are not two ends of one channel and must not
be designed as though they were.

## Goals

- Remote work appears in the invocation tree at full depth, not as an opaque span.
- No inbound path to the orchestrator that a stranger can reach.
- A dispatched job's cost lands in `model_calls` or the run is visibly incomplete.
- The night survives a job that never returns.

## Telemetry: why the recorder side was built first

`Recorder.ingest_external` exists and is tested, and reading it settles more of
the transport than it appears to.

It refuses an unknown dispatching invocation, so a report naming a parent that
does not exist writes nothing — forged or stale attribution fails closed rather
than creating orphaned rows. It resolves depth from the dispatcher's own depth,
so the tree the scrubber renders is correct without the job knowing where it sits
in it. It requires invocations parents-first and refuses a model call naming an
unrecorded invocation, so a partially delivered batch cannot half-write. And it
holds the recorder's lock, so ingest serializes through the single writer.

The transport therefore needs to do very little: authenticate, deserialize,
call it, and return the id mapping. **Almost every way to get this wrong is a way
of doing more than that** — a second database connection, a queue that reorders,
a retry that re-sends what was already written.

## The decision that shapes everything: how a job reaches the machine

Three shapes, and the third is the reason the first two are worth arguing about.

**Job joins the tailnet.** Ingest binds to the tailnet interface only and is
unreachable from the public internet; the machine's exposure does not change.
The cost is that an ephemeral job must acquire a tailnet identity, which means an
auth key reaching a container whose environment is visible in the Nebius console,
and ephemeral nodes accumulating in the tailnet unless they are cleaned up.

**Public authenticated endpoint.** Simplest to build and to debug. It puts a
listening service holding every captured idea on the public internet, defended by
one bearer token. The Privacy Airlock is the product's central claim, and "the
token was strong" is a weaker sentence than "it was never reachable."

**The job reports nothing, and the orchestrator reads.** Inverts the direction:
the job writes its telemetry alongside its artifacts, and `await_result` — which
already polls — collects it. No inbound path exists at all, and `ingest_external`
is called locally by the poller with the payload it fetched.

The third deserves the argument it has not yet had. It costs nothing in exposure,
it needs no credential inside the job, and idempotency becomes trivial because the
orchestrator decides when a payload is ingested rather than the job deciding when
to send it. What it costs is liveness: telemetry arrives when the job is
collected rather than as it happens, so a job that runs for twenty minutes
contributes nothing to the timeline until it finishes. Whether that matters
depends on whether the night scrubber is expected to show remote work in
progress — which `night-timeline` has not yet said.

The proposal's security marker asks the first-versus-second question because that
is how the roadmap framed it. This design records that the third option changes
the question, and should be answered alongside it.

## Batch, and why it changes the interface rather than a flag

`docs/MODELS.md` argues the night should use the Batch API: batch is exactly half
of standard across every model observed without exception, overnight work is the
definition of batchable, and cost per accepted artifact is a scored chart. The
morning interview stays on the standard API because a person is waiting.

The consequence is not a parameter. A batch submission is submit-then-poll, and a
standard completion is request-response — so a cloud `Reasoner` that supports
both is either two implementations behind one interface, or one implementation
whose `_do_complete` blocks on a poll and lies about being synchronous.

The interface already has the right shape for one of them. `Executor.dispatch` /
`await_result` **is** submit-then-poll. A batch reasoning turn is arguably an
`Executor` job rather than a `Reasoner` call, which would keep `Reasoner`
honestly synchronous and put every polled thing behind one interface.

That is the cleaner decomposition, and it rests on an unverified premise.

[NEEDS CLARIFICATION: Does Token Factory offer a Batch variant for Nemotron 3.5 Lightning and Nemotron 3 Super specifically — the pricing extract covered eleven other models and inferred the tariff — and if so, is a batch reasoning turn modeled as an `Executor` job rather than a `Reasoner` call?]

## Alternatives considered and rejected

**A stub executor now, the real one when credentials arrive.** Rejected. A stub
that returns plausible job results is indistinguishable in `model_calls` from a
real fan-out, and the fan-out is the evidence for the Nebius claim. Every other
stub in this codebase is visibly inert — `EchoReasoner` returns its own input —
and a stub that produced convincing data would be the first that could be
mistaken for the thing it stands in for.

**Telemetry inside `JobResult`.** Rejected by ADR 0004 and not reopened. It ties
the executor interface to a serialization format and makes a job that produced
artifacts but reported no telemetry look complete.

**Ingest writing through its own connection.** Rejected. The database's
concurrency model is one writer with a lock; a second connection is a second
writer, and the failure it produces is intermittent under exactly the load the
night generates.

**Dispatching from inside a request handler.** Rejected on the same grounds as
the brain's git calls: the one interaction that must never fail cannot depend on
a remote API.

## Consequences

- The `cloud` profile stops being a placeholder and becomes the judge instance's
  real configuration.
- `variant_group` and `variant_rank`, which the schema has carried since day 1,
  get their first writer.
- The demo's two-ideas-side-by-side comparison becomes readable from
  `model_calls` rather than asserted.
- ADR 0004's open risk closes with a new ADR naming the judge deployment target.
