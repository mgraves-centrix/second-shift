# telemetry

## ADDED Requirements

### Requirement: A night records what happened as it happens

A run SHALL write `events` rows as its work proceeds, so that the run is
renderable from its own record rather than only from generated data.

A stage beginning and ending, an invocation beginning and ending, and a failure
SHALL each be recorded. The lane an event records SHALL be the lane the work
belonged to.

#### Scenario: A real run is renderable
- **WHEN** a night completes and its timeline is requested
- **THEN** it returns events, and their lanes, rather than an empty timeline

#### Scenario: Stage boundaries are visible
- **WHEN** a stage starts and later ends
- **THEN** both are recorded, so the stage occupies a frame rather than an instant

#### Scenario: A failed stage is on the timeline
- **WHEN** a stage fails
- **THEN** the failure appears as an event with a severity, not only in the failure ledger

#### Scenario: A skipped stage is distinguishable
- **WHEN** a stage is skipped
- **THEN** the record shows it was skipped rather than omitting it
