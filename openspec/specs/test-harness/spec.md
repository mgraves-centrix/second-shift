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

### Requirement: Claims a machine can check are checked on every commit

The gate SHALL verify the claims about this repository that are mechanically
derivable from it, rather than leaving them to a periodic pass by a person.

It SHALL verify that a documented directory tree matches the filesystem in both
directions: every path it asserts exists, and every path it marks as planned
does not. A tree that asserts what is absent misleads a reader about what was
built; one that calls shipped work planned misleads them about what is left.

It SHALL verify a number stated in prose only where the prose says what the
number is derived from. Nothing may be inferred from prose: a checker that
guesses produces false positives, and a check that produces false positives is
one people learn to suppress.

It SHALL verify that a change still in flight cannot read as finished, and that
a capability's requirements are in force only if the change that added them was
archived.

It MUST state which claims it checked, because a passing check that is taken to
mean more than it does replaces a pass that would have found the rest.

#### Scenario: A documented path does not exist
- **WHEN** a tree asserts a directory that was never built
- **THEN** the gate fails and names it

#### Scenario: Shipped work is still marked planned
- **WHEN** a tree marks as planned a directory that now exists
- **THEN** the gate fails and names it, because the reader is being told work remains that does not

#### Scenario: A stated number stopped being true
- **WHEN** prose states a number, says what it derives from, and the derivation no longer produces it
- **THEN** the gate fails, naming the claim, the stated value and the real one

#### Scenario: A number with no stated derivation
- **WHEN** prose states a number without saying what it means
- **THEN** it is not checked and not reported, because inferring the meaning is how a checker starts crying wolf

#### Scenario: An unfinished change reads as finished
- **WHEN** an in-flight change has no unchecked task
- **THEN** the gate fails, because the listing that people read to decide what to do next would report it complete

#### Scenario: Requirements in force from a change that never archived
- **WHEN** a capability's canonical spec exists with no archived change that created it
- **THEN** the gate fails, because a requirement is binding while its proposal is still open

#### Scenario: The check does not overstate itself
- **WHEN** the check passes
- **THEN** it says which claims it verified, so that "the documents agree" is not read into a narrower result

### Requirement: A push carries a green gate, or is refused

Pushing SHALL be refused when the gate does not pass, rather than left to the
person pushing to have checked.

The refusal MUST name the way to proceed anyway, because an override somebody
cannot find is one they route around by disabling the mechanism entirely.

Removing a branch SHALL NOT be gated: a deletion has no tree to check, and
making it wait is the friction that gets the guard uninstalled.

The guard SHALL be tracked in the repository and enabled deliberately, so that
it is reviewable and arrives with a clone without installing itself.

#### Scenario: The gate is red
- **WHEN** a push is attempted while the gate fails
- **THEN** the push is refused, and what failed is on screen

#### Scenario: The gate is green
- **WHEN** the gate passes
- **THEN** the push proceeds

#### Scenario: Pushing anyway, on purpose
- **WHEN** somebody needs to push past a failure
- **THEN** the refusal has already told them how

#### Scenario: Deleting a branch
- **WHEN** a push removes a branch rather than adding commits
- **THEN** it is not gated, because there is no tree to check
