# test-harness Specification

## Purpose
Every gate this project has, run as one command in one order, by developers and
by CI alike — and shown to fail. The privacy gates run first; the night view is
exercised in a real browser against a real orchestrator; and defects that have
already shipped are reintroduced on every run so the gates that catch them
cannot quietly stop catching them.

## Requirements

### Requirement: One command runs every gate

The repository SHALL provide a single command that runs every gate in a fixed
order, stops at the first failure, and exits with that gate's exit code. CI
SHALL run that command rather than restating the gates.

#### Scenario: A failing gate stops the run with its own code
- **WHEN** a gate fails partway through
- **THEN** no later gate runs and the command exits with the failing gate's exit code

#### Scenario: CI runs the same definition
- **WHEN** the workflow runs
- **THEN** it invokes the gate command, and lists no gate of its own

### Requirement: The privacy gates run first

The airlock, policy and redaction tests SHALL be the first gate.

#### Scenario: A leak fails before the build
- **WHEN** a redaction test fails
- **THEN** the gate stops before the web build and browser test run

### Requirement: The night view is tested in a real browser

A browser test SHALL seed a night into a fresh database, serve it from a real
orchestrator on a free local port, and assert rendering from page geometry. It
SHALL need no network beyond localhost and no credential.

#### Scenario: A playhead drawn in the wrong place fails
- **WHEN** the playhead's drawn position does not follow the keyboard
- **THEN** the browser test fails, even where the slider's ARIA value is correct

#### Scenario: A missing orchestrator is named
- **WHEN** the orchestrator cannot start or does not answer
- **THEN** the test fails with a message saying so, not with a timeout

### Requirement: Shipped defects stay caught

The gate SHALL reintroduce each recorded defect and require its gate to fail.
A recorded defect whose target text no longer appears exactly once SHALL fail
the check.

#### Scenario: A reintroduced defect turns its gate red
- **WHEN** a recorded defect is reintroduced
- **THEN** the gate named for it fails, and the file is restored afterward

#### Scenario: A mutation that no longer applies is a failure
- **WHEN** the code a mutation targets has moved
- **THEN** the mutation check fails rather than reporting the defect caught
