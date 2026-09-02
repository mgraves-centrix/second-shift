## Purpose

Text completion from the model served on the always-on machine, behind the
`Reasoner` interface: the server's own token counts, its own words when it
fails, its output never guessed at, and the server itself supervised so it is
there in the morning.

## Requirements

### Requirement: Completion is served by the local model, behind the interface

Text completion on a local compute profile SHALL be produced by the configured
local inference server, reached only through the `Reasoner` interface.

The backend SHALL live in the providers package. No provider SDK, endpoint
detail or model identifier may appear outside it.

#### Scenario: A local profile completes against the server
- **WHEN** a completion is requested on a profile with a verified local reasoner
- **THEN** the request goes to the configured endpoint and the server's answer is returned to the caller

#### Scenario: The interface is the only route
- **WHEN** any part of the system outside the providers package needs a completion
- **THEN** it calls `Reasoner.complete` and cannot name the backend, its endpoint or its model

#### Scenario: Local completion is not remote
- **WHEN** a completion is requested under `local-only`
- **THEN** it is permitted, recorded as a local provider, and costs nothing

### Requirement: Token accounting is disjoint and taken from the server

Token counts SHALL be read from the server's own usage report, never estimated.
Prompt, completion and reasoning counts MUST be disjoint, because they are summed
into a total.

#### Scenario: Counts come from the server
- **WHEN** the server reports usage for a completion
- **THEN** those counts are what is recorded, rather than a count derived from text length

#### Scenario: Reasoning tokens are not double counted
- **WHEN** the server reports reasoning tokens nested inside its completion count
- **THEN** the recorded completion count excludes them and the recorded reasoning count carries them, so the total is the number of tokens actually generated

### Requirement: Model output is never silently discarded

Where the server separates reasoning from the answer as structured fields, both
SHALL be reported as what they are. Where it does not, the text SHALL be returned
unmodified.

The provider MUST NOT infer the boundary between reasoning and answer from the
text itself.

#### Scenario: The server separates reasoning
- **WHEN** the response carries reasoning as its own field
- **THEN** the answer is returned as the completion and the reasoning is reported as reasoning tokens

#### Scenario: The server does not separate reasoning
- **WHEN** the model emits its reasoning inline and the response carries no separate field
- **THEN** the text is returned whole, because a guessed boundary would delete the answer whenever it guessed wrong

### Requirement: A completion that did not stop cleanly is visible

A completion that ended for any reason other than the model finishing SHALL be
recorded as such. Truncation MUST NOT be presented as a completed answer.

#### Scenario: Truncated at the token limit
- **WHEN** the server reports that generation stopped at the token limit
- **THEN** the completion is returned and a warning is recorded naming the reason

#### Scenario: A clean stop records nothing extra
- **WHEN** generation ends because the model finished
- **THEN** no warning is recorded

### Requirement: A failing backend fails loudly and is recorded

A backend that is unreachable, times out, refuses the request, or answers with
something that is not a completion SHALL raise, naming the endpoint. The failure
MUST be recorded before it propagates.

A failed call MUST NOT be recorded as a successful model call, and MUST NOT
return a substitute answer.

#### Scenario: The server is unreachable
- **WHEN** the configured endpoint refuses the connection
- **THEN** the call raises naming the endpoint, a failure is recorded and classified as a network failure, and no model call row is written

#### Scenario: The server does not answer in time
- **WHEN** the request exceeds the configured timeout
- **THEN** the call raises and the recorded failure is classified as a model timeout

#### Scenario: The server answers with an error
- **WHEN** the server returns an error status
- **THEN** the call raises carrying the server's own message, so a cause the server named is classified from its own words

#### Scenario: The answer is not a completion
- **WHEN** the response cannot be read as a completion
- **THEN** the call raises and the recorded failure is classified as bad output, rather than a substitute answer being returned

#### Scenario: No substitute is returned
- **WHEN** any of these failures occurs
- **THEN** nothing is returned to the caller, because a fabricated answer recorded as a model call is indistinguishable in the data from a real one

### Requirement: Endpoint, model and sampling are configuration

The endpoint, the served-model name, sampling parameters and the request timeout
SHALL be read from configuration. Changing any of them MUST NOT require a code
change.

#### Scenario: The endpoint is configured
- **WHEN** the server is moved to a different host or port
- **THEN** configuration alone redirects both the probe and the provider

#### Scenario: Repeated sampling can vary
- **WHEN** the same prompt is completed several times, as an eval run does
- **THEN** sampling is configured such that the outputs may differ, so a reported spread measures the system rather than the sampler

### Requirement: The inference server survives a reboot

The local inference server SHALL be supervised, started at boot, and restarted
when it exits.

It MUST listen on the port allocated for it in configuration, which is not the
port an ad-hoc server would claim by default.

#### Scenario: The machine reboots
- **WHEN** the always-on machine restarts
- **THEN** the inference server is started again without anyone logging in

#### Scenario: The server exits
- **WHEN** the server process exits for any reason
- **THEN** it is restarted

#### Scenario: The allocated port is used
- **WHEN** the supervised server starts
- **THEN** it is reachable on the port the configuration allocates to the local reasoner, which the capability probe checks
