## ADDED Requirements

### Requirement: What a night learned is retrievable memory

The index SHALL include each night's distillation from the brain, and SHALL
read it at a run's pinned commit where one is given.

#### Scenario: A night's distillation is available to a later run
- **WHEN** the index is built after a night has distilled what it learned
- **THEN** that distillation is a document, attributed to the run that produced it

### Requirement: A document's policy comes from its own origin

A document derived from one entry SHALL carry that entry's policy. A night's
distillation SHALL carry the stricter of its run's effective policy and its
entry's policy. A document whose origin cannot be resolved SHALL carry
`local-only`.

#### Scenario: A private night does not reach a cloud-assisted run
- **WHEN** a night of a `local-only` entry is indexed and a `cloud-assisted` run assembles context
- **THEN** that night's distillation is not among the pieces returned

#### Scenario: A widened run keeps the stricter policy
- **WHEN** a `local-only` entry's run was widened to `cloud-assisted` by a decision
- **THEN** that night's distillation carries `local-only`

#### Scenario: An origin that cannot be resolved is private
- **WHEN** a night file names a run the database does not hold
- **THEN** its distillation carries `local-only`

### Requirement: Answered questions and outcomes are memory

The index SHALL include decisions the person answered and recorded outcomes,
each under its entry's policy. An unanswered decision SHALL NOT be indexed.

#### Scenario: An answered question is available to a later run
- **WHEN** a question on an entry has been answered
- **THEN** the question and its answer are one document under that entry's policy

#### Scenario: An unanswered question is not memory
- **WHEN** a question is open
- **THEN** it is not indexed
