## Purpose

A complete, queryable record of what every agent did, which model it used, what
that cost, and how it failed — captured from the first run so that eight weeks
of trend data has no gaps.

## ADDED Requirements

### Requirement: Agent invocations form a tree

The system SHALL record every agent turn as an `agent_invocations` row, and MUST
preserve parentage when an agent invokes another agent.

Invocation lifecycle MUST be owned by a context manager, so that an invocation
is closed exactly once even when the body raises.

#### Scenario: Nested invocation
- **WHEN** a researcher agent invokes a critic agent, which invokes a distiller
- **THEN** three invocations are recorded with correct `parent_invocation_id` links and depths of 0, 1 and 2

#### Scenario: Invocation raises
- **WHEN** an agent's body raises an exception
- **THEN** the invocation is closed with `outcome = 'failed'`, `ended_at_ms` is set, and a typed `failures` row is written

#### Scenario: Concurrent sibling invocations
- **WHEN** a parent agent invokes three children concurrently as asyncio tasks
- **THEN** all three record the same `parent_invocation_id` and none inherits another sibling's context

### Requirement: Every model call is recorded

The system SHALL write a `model_calls` row for every completion, recording
provider, model, token counts, latency, estimated cost, and the policy under
which it ran. Recording MUST be performed by the provider base class, not by
individual implementations.

#### Scenario: Successful completion
- **WHEN** a reasoner returns a completion
- **THEN** a `model_calls` row exists, linked to the current invocation, with prompt, completion and total token counts and a non-null latency

#### Scenario: Implementation cannot skip instrumentation
- **WHEN** a new provider implementation is added that overrides only its internal completion method
- **THEN** telemetry is recorded without that implementation containing any telemetry code

### Requirement: Cost is computed from versioned rates

The system SHALL compute `estimated_cost_usd` at write time from a git-tracked
rate table keyed by provider and model, where each entry carries an
`effective_from` date. The rate in effect at the call's timestamp MUST be the
one applied.

A missing rate SHALL be a loud failure. The system MUST NOT record zero or a
guessed cost, because the cost curve is a measurement rather than a display
value.

#### Scenario: Rate applied at write time
- **WHEN** a model call completes for a provider and model present in the rate table
- **THEN** `estimated_cost_usd` is computed from the rate effective at the call's timestamp

#### Scenario: Missing rate
- **WHEN** a model call completes for a provider and model absent from the rate table
- **THEN** the call is reported as a typed failure and no cost is silently recorded as zero

#### Scenario: Historical reproducibility
- **WHEN** rates change and a new entry is added with a later `effective_from`
- **THEN** costs already recorded are unchanged, and the rate that produced any historical cost is recoverable from the repository

### Requirement: Telemetry can be attributed to out-of-process work

The recorder SHALL accept telemetry attributed to work executed outside the
orchestrator process, attaching it under the invocation that dispatched that
work, so remote work appears in the tree at full depth rather than as an opaque
span.

All such telemetry MUST be serialized through the orchestrator's own writer. No
external caller may open its own connection to the database.

The authenticated transport that carries this telemetry from a remote job is
delivered with the Nebius executor, not here. This requirement covers the
recorder-side contract that transport depends on.

#### Scenario: Remote work attaches under its dispatcher
- **WHEN** telemetry is submitted for work dispatched from a known invocation
- **THEN** the recorded invocations and model calls attach under that invocation with correct parentage and depth

#### Scenario: Concurrent dispatches remain distinct
- **WHEN** telemetry arrives for five jobs dispatched concurrently from five different invocations
- **THEN** each job's rows attach under its own dispatching invocation, and no job's work is attributed to another

#### Scenario: Submissions serialize through one writer
- **WHEN** externally-attributed telemetry is submitted while the orchestrator is writing
- **THEN** the write is serialized through the orchestrator's writer rather than a second connection

#### Scenario: Unknown dispatcher is rejected
- **WHEN** telemetry is submitted naming an invocation that does not exist
- **THEN** the submission is rejected and no orphaned rows are written

### Requirement: Tool calls record redacted queries only

The system SHALL record every external tool call with its endpoint, credits
consumed, result count and latency. The stored query MUST be the
policy-redacted form; a raw query MUST NOT be persisted.

#### Scenario: Search under local-only policy
- **WHEN** a Tavily search runs for a `local-only` entry
- **THEN** a `tool_calls` row records the redacted query and the raw query appears nowhere in the database

### Requirement: Failures are typed and deduplicated

The system SHALL classify every failure into the defined taxonomy and record a
normalized signature so recurrence can be derived.

#### Scenario: Classified failure
- **WHEN** a model call exceeds its timeout
- **THEN** a `failures` row is written with `type = 'model_timeout'` and a signature stable across repeats of the same condition

#### Scenario: Unclassifiable failure
- **WHEN** an error arises that matches no taxonomy entry
- **THEN** the failure is still recorded with the closest applicable type and the original message preserved, rather than being dropped

### Requirement: Events are renderable without parsing

The system SHALL write `events` rows with pre-rendered `lane`, `kind`, `label`
and `severity` columns. Detailed payloads MUST be stored separately so that
timeline rendering never requires parsing JSON.

#### Scenario: Dense night playback
- **WHEN** the night view requests events for a six-hour run
- **THEN** every row needed to draw the timeline is available from scalar columns without reading `payload_json`
