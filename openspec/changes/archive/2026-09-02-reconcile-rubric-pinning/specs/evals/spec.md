## ADDED Requirements

### Requirement: Scoring refuses a rubric that is not the one pinned

Scoring an eval run SHALL compare the hash of the rubric it was given against the
`rubric_sha` recorded on that run, before any output is generated. Where they
differ, scoring MUST fail, naming both hashes, and MUST record no results.

A rubric mismatch is not a failed sample. Every sample under a different rubric is
wrong in the same way, so it MUST NOT be recorded as a partial run.

#### Scenario: The rubric on disk is not the rubric pinned
- **WHEN** a run recorded under one rubric is scored with a different one
- **THEN** scoring fails before generating anything, names the run and both hashes, and writes no results and no partial run

#### Scenario: The rubric on disk is the rubric pinned
- **WHEN** a run is scored with the rubric whose hash it recorded
- **THEN** scoring proceeds and results are recorded as normal

#### Scenario: A mismatch is not recorded as a failed sample
- **WHEN** scoring is refused because the rubric does not match
- **THEN** no failure row is written for the individual samples, because the run did not partially succeed

### Requirement: The pinned rubric is reportable beside the file on disk

Status SHALL report every recorded eval run with its pinned rubric hash, its brain
commit, its week, and whether it is awaiting scoring — alongside the hash of the
rubric file currently on disk.

Where any recorded run's pinned rubric is not the file on disk, status MUST say so
explicitly and MUST exit non-zero. Reconciling a pinned hash MUST NOT require
reading the database by hand.

#### Scenario: Recorded runs and their pinning are reported
- **WHEN** status runs against a database holding an eval run
- **THEN** that run's id, week, pinned rubric hash, brain commit and awaiting-scoring state are printed, together with the hash of the rubric file on disk

#### Scenario: A run pinned to a different rubric is called out
- **WHEN** a recorded run's pinned rubric hash is not the hash of the rubric on disk
- **THEN** status states that the pinned rubric is not the file on disk, names both hashes, and exits non-zero

#### Scenario: Agreement is reported as agreement
- **WHEN** every recorded run pins the rubric currently on disk
- **THEN** status reports that they agree and exits zero

#### Scenario: No recorded runs
- **WHEN** status runs against a database with no eval runs
- **THEN** it reports the rubric on disk, states that no run has pinned it yet, and exits zero

### Requirement: Deployment does not silently replace a rubric that differs

Deployment SHALL compare the rubric on the target against the rubric being
shipped before replacing the target tree. Where they differ, deployment MUST stop
before anything is destroyed, name both hashes, and state how to retrieve the
target's copy.

Proceeding past a difference SHALL require an explicit override. An absent rubric
on the target is not a difference; an indeterminate one MUST NOT be treated as
absent.

#### Scenario: The target holds a rubric that differs
- **WHEN** deployment runs against a target whose rubric differs from the one being shipped
- **THEN** it stops before replacing the tree, prints both hashes, and names both the command that retrieves the target's copy and the override that would proceed anyway

#### Scenario: The target holds the same rubric
- **WHEN** the target's rubric is identical to the one being shipped
- **THEN** deployment proceeds without comment

#### Scenario: The target holds no rubric
- **WHEN** the target has no rubric file, as on a first deployment
- **THEN** deployment proceeds

#### Scenario: The override is explicit
- **WHEN** the operator sets the documented override and the rubrics differ
- **THEN** deployment proceeds, having stated that it is replacing a differing rubric
