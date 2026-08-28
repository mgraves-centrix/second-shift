## Purpose

A complete synthetic night: dense enough to build a timeline against,
reproducible enough to rehearse, and permanently excluded from measurement.

## Requirements


### Requirement: A generated night is dense enough to render

The generator SHALL produce a night spanning several hours containing at least
several hundred timeline events distributed across multiple lanes, a run with
its stages, an invocation tree at least three levels deep, and artifacts grouped
into ranked variants.

#### Scenario: A night is generated
- **WHEN** a night is generated
- **THEN** it contains a run, its stages, an invocation tree of depth three or more, and at least four hundred events across more than one lane

#### Scenario: Events span the night
- **WHEN** the generated events are ordered by time
- **THEN** they span several hours rather than clustering at one instant

#### Scenario: Variants are grouped and ranked
- **WHEN** the generated artifacts are inspected
- **THEN** several belong to one variant group with distinct ranks

### Requirement: Generation is deterministic

The same seed SHALL produce the same night. Identifiers, timings, token counts
and costs MUST all be reproducible.

#### Scenario: Same seed, same night
- **WHEN** a night is generated twice with the same seed into separate databases
- **THEN** the two are identical in every generated value

#### Scenario: Different seeds differ
- **WHEN** two nights are generated with different seeds
- **THEN** they differ

### Requirement: Every generated row is marked synthetic

Every row the generator writes SHALL carry the synthetic flag, so measurement
excludes it and dispatch never acts on it.

#### Scenario: Measurement excludes a generated night
- **WHEN** a night is generated into a database that also holds real work
- **THEN** the cost and totals views report nothing attributable to it

#### Scenario: Generated entries are never dispatched
- **WHEN** a generated night includes queued entries
- **THEN** those entries are absent from the set eligible for a run

#### Scenario: Generated events remain renderable
- **WHEN** a timeline is requested for a generated run
- **THEN** its events are returned, so the view and the judge deployment can render seeded data

### Requirement: Generated data satisfies the same constraints as real data

The generator SHALL write through the repository layer, so generated work obeys
every constraint real work obeys.

#### Scenario: The airlock accepts generated local-only work
- **WHEN** a generated run executes under local-only policy
- **THEN** its model calls name only local providers, and the database accepts them

#### Scenario: Generated telemetry is shaped like real telemetry
- **WHEN** generated invocations and model calls are queried
- **THEN** they satisfy the same queries the real night view uses, with the same columns populated

### Requirement: A generated night includes failure

The generator SHALL produce typed failures within a night, because a night
without them does not resemble a real one and the failure ledger is a view worth
rendering.

#### Scenario: Failures appear and are typed
- **WHEN** a night is generated
- **THEN** it contains failures drawn from the defined taxonomy, attached to invocations

#### Scenario: Generated failures do not pollute the real ledger
- **WHEN** the failure ledger is queried
- **THEN** generated failures are absent from it
