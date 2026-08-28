## MODIFIED Requirements

### Requirement: The capability probe reports a set, not a boolean

The probe SHALL check for CUDA availability, local inference endpoint
reachability, and speech-stack importability independently, reporting each
result separately so that a partial stack is visible rather than collapsing to a
single yes or no.

Endpoint reachability is not sufficient evidence of a local reasoner. The probe
SHALL ask a reachable endpoint which model it serves and compare that against
the expected local binding. An endpoint serving anything else MUST be reported
unavailable, with a reason naming the model actually found.

The expected model identifier SHALL be configuration rather than a constant,
because the served name is chosen when the server is started.

#### Scenario: Partial local stack
- **WHEN** CUDA is present but the local inference endpoint is unreachable
- **THEN** the probe reports CUDA available and the endpoint unavailable as distinct findings

#### Scenario: Partial stack degrades rather than aborting
- **WHEN** the probe reports an incomplete local stack
- **THEN** the profile resolves to `cloud`, startup proceeds, and the findings that caused the degradation are recorded and readable at runtime

#### Scenario: Endpoint serving the expected model
- **WHEN** the endpoint is reachable and reports the expected model identifier
- **THEN** the local reasoner is reported available

#### Scenario: Endpoint serving a different model
- **WHEN** the endpoint is reachable but reports a model other than the expected one
- **THEN** the local reasoner is reported **unavailable**, and the reason names the model found and the one expected

#### Scenario: Endpoint that cannot be identified
- **WHEN** the endpoint accepts a connection but does not answer a model-identity query
- **THEN** the local reasoner is reported unavailable rather than assumed present

#### Scenario: Identity failure does not abort startup
- **WHEN** an endpoint is serving an unexpected model
- **THEN** the profile degrades to `cloud` and startup proceeds, exactly as for an unreachable endpoint
