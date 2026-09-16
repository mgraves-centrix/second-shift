## ADDED Requirements

### Requirement: A night does not run against a placeholder reasoner

The night command SHALL refuse to start, dispatching nothing, where the
resolved profile has no reasoner that can do the work or a backend cannot be
bound, and SHALL say why.

#### Scenario: A cloud deployment with no cloud reasoner refuses
- **WHEN** the night command runs on the `cloud` profile before a cloud reasoner exists
- **THEN** it exits non-zero naming the reason, opens no run, and leaves every entry queued

### Requirement: An interrupted night is recovered by the next one

Before dispatching, the night command SHALL close every open non-synthetic stage
and run as `failed` and return every `running` entry to `queued`. Only one night
SHALL run against a database at a time, and recovery SHALL happen only under
that exclusion.

#### Scenario: A killed night's idea is worked again
- **WHEN** a night is killed with an entry `running` and its run and stage open
- **THEN** the next night closes the run as `failed`, reports it, and works the entry again

#### Scenario: A second night refuses rather than recovering
- **WHEN** a night is started while another holds the database
- **THEN** it exits non-zero and closes nothing

### Requirement: One entry's defect does not end the night

An error escaping one entry SHALL be recorded, and the night SHALL continue with
the remaining entries and exit non-zero.

#### Scenario: A later entry still runs
- **WHEN** the first entry of a night raises an unexpected error
- **THEN** the next entry is worked and the command exits non-zero naming the first

### Requirement: A stage that wrote nothing is not complete

A stage whose output could not be landed, including a fan-out that landed no
variant, SHALL be recorded `failed`, and no error on a stage's write path SHALL
leave its row `running`.

#### Scenario: A fan-out with no file landed
- **WHEN** every variant write of a stage fails
- **THEN** the stage is `failed`

### Requirement: A stage failure is recorded against its run

A failure recorded for a stage SHALL name the run, so the briefing can report
why the stage failed.

#### Scenario: The reason reaches the morning
- **WHEN** a stage fails because its model call raised
- **THEN** the briefing reports that stage as failed with the error's message
