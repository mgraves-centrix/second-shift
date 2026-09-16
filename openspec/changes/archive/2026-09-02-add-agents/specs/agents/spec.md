## Purpose

The roster of six fixed roles, their versioned prompt files, and the path from
a role to a recorded model call — so that an eight-week curve can be shown to
measure the brain rather than a prompt that changed underneath it.

## ADDED Requirements

### Requirement: Every registered agent pins its prompt by content

An agent's `prompt_sha` SHALL be computed from the content of the file at its
`prompt_path` at registration. It MUST NOT be supplied by the caller, defaulted,
or derived from anything other than that file's bytes.

#### Scenario: The recorded hash is the file's hash
- **WHEN** an agent is registered against a prompt file
- **THEN** the recorded `prompt_sha` equals the SHA-256 of that file's content

#### Scenario: Editing the prompt changes the recorded hash
- **WHEN** a prompt file's content changes and the agent is registered again
- **THEN** the newly recorded `prompt_sha` differs from the previous one

### Requirement: A missing prompt file fails registration loudly

Registering an agent whose `prompt_path` does not exist SHALL raise, and MUST
NOT write a roster row. A row naming a file that is not there records a
provenance that cannot be checked.

#### Scenario: Registration against an absent file
- **WHEN** an agent is registered against a path that does not exist
- **THEN** the registration raises and no `agents` row is written

### Requirement: Prompt files are append-only and the filename carries the version

A prompt file SHALL NOT be edited in place once registered. A changed prompt is
a new file at the next version, and registration SHALL refuse a file whose
content no longer matches the `prompt_sha` recorded for that version.

#### Scenario: An edited file at an already-registered version is refused
- **GIVEN** an agent registered at version 1 with a recorded hash
- **WHEN** that version's prompt file has been edited and registration runs again
- **THEN** registration raises, naming both the recorded and the current hash

#### Scenario: A new version registers alongside the old
- **WHEN** a prompt is superseded by a file at the next version and registered
- **THEN** both versions exist in the roster, each pinned to its own file

### Requirement: The roster covers every role the schema permits

The roster SHALL contain exactly one active agent for each role the `agents`
table's CHECK constraint permits, and MUST NOT introduce a role outside it.

#### Scenario: Every permitted role is registered
- **WHEN** the roster is registered and the permitted roles are read from the schema
- **THEN** each role has exactly one active agent

### Requirement: An invocation records its work through the existing machinery

An agent invocation SHALL open an `agent_invocations` row with parentage and
depth from the surrounding context, and any model call it makes SHALL be
recorded. The agent MUST NOT write telemetry itself.

#### Scenario: An invocation is recorded with its parentage
- **WHEN** an agent is invoked inside a run
- **THEN** an `agent_invocations` row exists for it carrying that run and the expected depth

#### Scenario: The model call is recorded
- **WHEN** an invoked agent completes a reasoner call
- **THEN** a `model_calls` row exists naming the policy the invocation ran under

### Requirement: An agent passes its policy explicitly

An agent SHALL pass the policy it is invoked under to the reasoner on every
call. It MUST NOT default a policy or infer one from ambient state.

#### Scenario: A local-only invocation cannot reach a remote provider
- **WHEN** an agent is invoked under `local-only` against a remote provider
- **THEN** the call is refused before the provider is reached, and no `model_calls` row is written
