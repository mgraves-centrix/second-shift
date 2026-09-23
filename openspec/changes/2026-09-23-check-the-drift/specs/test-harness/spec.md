# test-harness

## ADDED Requirements

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
