# Project Constitution

Immutable principles for Second Shift. Every proposal is checked against these
before scaffolding, and every implementation step is checked against them again
before code is written.

A violation is a **CRITICAL BLOCKING FINDING**. It is not a warning and not a
suggestion. Work stops until the violation is resolved, or until the user
explicitly overrides it on the record — naming the principle being crossed and
what is being traded for it.

These are derived from `docs/ARCHITECTURE.md` and the accepted ADRs in
`docs/decisions/`. Changing a principle here means writing an ADR that
supersedes the one that established it.

---

## 1. The Brain Is Plaintext Under Git

Memory MUST be human-readable markdown in a git-versioned repository. Skills,
style guide, failure ledger and profile are diffable text.

Memory MUST NOT be buried in an opaque store. No mem0, Letta or Zep. The brain
lives in its own repository, sibling to this one — never vendored in, because
nightly automated commits would bury the human commit history that evidences
when this project was built. (ADR 0001)

**Violation looks like:** memory that can only be read through an API; a
retrieval store that is the source of truth rather than an index over the
markdown; brain files committed into this repo.

## 2. The Privacy Airlock

Every idea carries a policy. `local-only` never leaves the machine.
`cloud-assisted` passes a redaction step before any egress.

Retrieval MUST happen locally on every compute profile. Only assembled,
policy-filtered context is ever eligible to leave. The brain itself never
leaves.

A `local-only` idea MUST NOT reach a remote provider. This is enforced as a
`CHECK` constraint on `model_calls`, not as a convention — any code path that
would violate it fails at the database. Proposals MUST NOT weaken, bypass or
make that constraint conditional.

`local-only` is a hardware capability, not a preference. Where a compute profile
cannot honor it, the UI MUST say so rather than silently downgrading the policy.
(ADR 0003)

**Violation looks like:** raw entry text in a Tavily query; retrieval delegated
to a hosted embedding endpoint; a redaction step that is skippable by
configuration; an export path that includes `model_call_payloads`. (ADR 0007)

## 3. No Empty Mornings

The night pipeline MUST be a checkpointed state machine. Each stage commits its
output as it completes, independently of what happens afterward.

If a late stage fails, the morning MUST still present every stage that
succeeded, plus the questions the run got stuck on. Graceful degradation is
correct behavior, not a failure state.

**Violation looks like:** a stage that holds its output until the whole run
completes; an all-or-nothing transaction across stages; a morning view that
renders an error instead of partial results.

## 4. Text-First, Voice Layered On

Every voice interaction MUST have a working text equivalent that is not a
degraded fallback.

TTS and ASR MUST NOT be on the critical path of any feature. Voice upgrades a
working text path; it never gates one.

**Violation looks like:** a briefing that only exists as audio; an interview
turn that cannot be completed by typing; a feature blocked on an unproven
speech dependency.

## 5. One Codebase, Two Deployments

The personal instance and the judge instance MUST be the same code, separated
only by compute profile. Never a fork, never a branch, never a
`if DEMO_MODE` divergence in business logic.

All compute MUST sit behind the `Transcriber` / `Reasoner` / `Embedder` /
`Executor` interfaces. Provider specifics MUST NOT leak into agents, the night
state machine, or the API layer. (ADR 0003)

The judge instance MUST contain zero real data and MUST be labeled in-UI as a
demo.

**Violation looks like:** a provider SDK imported outside `providers/`; a code
path that exists only for the demo; synthetic rows without `is_synthetic = 1`.

## 6. Scope Boundary — Idea In, Artifact Out, Memory In Between

Proposals MUST NOT introduce anything listed in `NOT_BUILDING.md`: calendar,
email, meeting capture, day planning, task management, wake words, multi-user,
or a general chat interface.

A request for one of these is refused by default. It proceeds only after an
explicit override that names the line being crossed and what is being cut to pay
for it — and the entry then moves out of `NOT_BUILDING.md` rather than being
silently deleted from it.

**Violation looks like:** a proposal that quietly adds a todo list because a
decision "needed tracking"; an open chat box that becomes the primary interface
and replaces the structured interview.

## 7. Telemetry From Line One

Every agent invocation and every model call MUST be logged from the first run,
including during development. Every telemetry row MUST record the policy it ran
under.

Telemetry MUST NOT be deferred, sampled, or added after a feature works.
Retrofitted instrumentation leaves gaps exactly where the eight-week trend needs
continuity, and that data cannot be backfilled.

Any table that accumulates evidence MUST carry `is_synthetic` so development and
seed data can never contaminate a measurement.

**Violation looks like:** a provider call that returns without writing
`model_calls`; a new agent that does not open an `agent_invocations` row; a
rollup view that forgets to filter `is_synthetic = 0`.
