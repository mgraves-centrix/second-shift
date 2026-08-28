## Purpose

Bind all compute to four narrow interfaces selected by a resolved profile, so
the DGX Spark is a capability tier rather than a requirement and the same
codebase runs unmodified for a person who owns no accelerator.

## Requirements

### Requirement: Profile resolution is deterministic and recorded

The system SHALL resolve a compute profile at startup in this order: the
`SECOND_SHIFT_PROFILE` environment variable, then a capability probe, then
`cloud` as the default. The resolved profile and the probe's findings MUST be
recorded, and the profile MUST be stamped onto every run and model call.

#### Scenario: Explicit override
- **WHEN** `SECOND_SHIFT_PROFILE=cloud` is set on a machine with a working local stack
- **THEN** the profile resolves to `cloud` and no probe result overrides it

#### Scenario: No accelerator present
- **WHEN** the application starts on a machine with no CUDA device and no local endpoint
- **THEN** the profile resolves to `cloud`

#### Scenario: Attribution after the fact
- **WHEN** a model call has been recorded
- **THEN** the profile under which it ran can be read from the row without consulting external state

### Requirement: The capability probe reports a set, not a boolean

The probe SHALL check for CUDA availability, local inference endpoint
reachability, and speech-stack importability independently, reporting each
result separately so that a partial stack is visible rather than collapsing to a
single yes or no.

#### Scenario: Partial local stack
- **WHEN** CUDA is present but the local inference endpoint is unreachable
- **THEN** the probe reports CUDA available and the endpoint unavailable as distinct findings

#### Scenario: Partial stack degrades rather than aborting
- **WHEN** the probe reports an incomplete local stack
- **THEN** the profile resolves to `cloud`, startup proceeds, and the findings that caused the degradation are recorded and readable at runtime

### Requirement: Compute is reached only through provider interfaces

All compute SHALL be accessed through the `Transcriber`, `Reasoner`, `Embedder`
and `Executor` interfaces. Provider-specific SDKs, model identifiers and
endpoint details MUST NOT appear outside the providers package.

#### Scenario: Registry binds by profile
- **WHEN** the profile resolves to `cloud`
- **THEN** the registry returns cloud-backed implementations for every interface, and no local backend is constructed

#### Scenario: No provider leakage
- **WHEN** the agents, night state machine or API packages are inspected
- **THEN** no provider SDK is imported and no model identifier is hardcoded outside the providers package

### Requirement: Dispatched work carries its telemetry context

`Executor.dispatch` SHALL carry a telemetry descriptor identifying where
out-of-process telemetry is sent and which invocation it attaches under.

`JobResult` MUST NOT be the transport for telemetry, so that the Executor
interface stays independent of any telemetry serialization format.

#### Scenario: Dispatch carries the descriptor
- **WHEN** a job is dispatched from within an active invocation
- **THEN** the descriptor passed to the executor identifies the ingest destination, its credential, and the dispatching invocation id

#### Scenario: Result carries no telemetry payload
- **WHEN** a job completes and returns its result
- **THEN** the result contains the work product only, and no telemetry records

### Requirement: Interfaces are instrumented by the base class

Each provider interface SHALL record its own telemetry in the base class.
Implementations override an internal method only.

#### Scenario: Adding a backend
- **WHEN** a new reasoner backend is implemented against the interface
- **THEN** its calls appear in `model_calls` without the implementation containing telemetry code
