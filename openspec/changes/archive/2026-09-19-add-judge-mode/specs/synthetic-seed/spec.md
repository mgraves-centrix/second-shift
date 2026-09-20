# synthetic-seed

## ADDED Requirements

### Requirement: A seeded night includes the questions it got stuck on

A generated night SHALL raise open decisions, so that a deployment rendering
seeded data has an interview to conduct rather than an empty agenda.

#### Scenario: The morning has an agenda
- **WHEN** a briefing is assembled over a seeded night
- **THEN** it contains open questions, each with its rationale

#### Scenario: A question that would widen policy is marked
- **WHEN** a seeded question is raised against a `local-only` entry
- **THEN** it is marked as one whose answer can send the idea off the machine

#### Scenario: The questions are deterministic
- **WHEN** the same seed is generated twice
- **THEN** the same questions are raised in the same order

### Requirement: Seeded artifacts have content

A generated artifact SHALL have bytes on disk matching its recorded hash, so an
interface that offers to open one is not offering something that is not there.

#### Scenario: A seeded artifact can be opened
- **WHEN** an artifact from a seeded night is requested
- **THEN** its content is returned

#### Scenario: Its recorded hash describes what landed
- **WHEN** a seeded artifact's hash is compared against the file
- **THEN** they agree
