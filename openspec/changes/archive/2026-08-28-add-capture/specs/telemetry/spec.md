## ADDED Requirements

### Requirement: Events may attach to an entry

An event SHALL be able to name the entry it concerns, independently of any run
or invocation. Events that occur at capture time have neither, and without this
they are recorded with no readable attachment or not recorded at all.

Queries that retrieve an entry's history MUST return these events.

#### Scenario: Capture-time event is readable
- **WHEN** an event is recorded during capture, before any run exists
- **THEN** it names the entry, and retrieving that entry's history returns it

#### Scenario: An event may name both an entry and a run
- **WHEN** an event occurs during a run that is working on a known entry
- **THEN** it may name both, and appears in both the run's timeline and the entry's history

#### Scenario: Existing timeline behavior is unchanged
- **WHEN** a run's timeline is retrieved
- **THEN** it returns the run's events as before, whether or not they name an entry
