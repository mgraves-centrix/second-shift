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
