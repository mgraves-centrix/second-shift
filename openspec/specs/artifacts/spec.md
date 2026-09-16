# artifacts Specification

## Purpose
The middle term of "idea in, artifact out, memory in between": work products
that land as files a person can open in the tool that edits that kind of file,
recorded so that what the database says about an artifact is derived from the
bytes rather than from what was meant to be written — and variant groups whose
rank is the critic's ordering rather than the order things happened to be
generated in.

## Requirements

### Requirement: An artifact is a file, and its record describes what landed

Every artifact row SHALL correspond to bytes on disk. `content_sha` and `bytes`
SHALL be computed from the file as read back after writing, not from the value
that was intended to be written.

#### Scenario: The recorded hash is the hash of the file on disk
- **WHEN** an artifact is written
- **THEN** its recorded `content_sha` equals the SHA-256 of the file's bytes and its recorded `bytes` equals the file's size

#### Scenario: A corrupted file no longer matches its record
- **WHEN** an artifact's file is modified after it was recorded
- **THEN** verifying it against its recorded hash reports a mismatch

#### Scenario: A failed write records nothing
- **WHEN** writing an artifact's file fails
- **THEN** no artifact row exists for it

#### Scenario: An artifact resolves to the invocation that produced it
- **WHEN** an artifact is written during a stage
- **THEN** its `produced_by_invocation_id` names that stage's invocation, and the artifacts of an invocation can be found from it

### Requirement: Group, index and rank are three distinct things

`variant_group` SHALL identify a set of variants, `variant_index` SHALL identify
each variant within it, and `variant_rank` SHALL carry only an ordering a critic
produced. `variant_rank` SHALL NOT be derived from `variant_index`.

#### Scenario: Rank is not a copy of the generation order
- **WHEN** a variant group is ranked by a critic whose ordering differs from the generation order
- **THEN** the recorded ranks reflect the critic's ordering rather than the indices

#### Scenario: Variants of one fan-out share a group
- **WHEN** several variants are produced for one thing
- **THEN** they share a `variant_group` and each carries a distinct `variant_index`

#### Scenario: An unranked group carries no ranks
- **WHEN** no critic ordering is available for a variant group
- **THEN** every variant in it has a null `variant_rank`, rather than a rank equal to its index

### Requirement: A partial ranking is refused rather than applied

Where a critic's ordering does not cover exactly the variants in a group, no rank
SHALL be written for that group.

#### Scenario: An ordering that omits a variant is refused
- **WHEN** a critic's ordering names fewer variants than the group contains
- **THEN** no variant in the group receives a rank

#### Scenario: An ordering that repeats a variant is refused
- **WHEN** a critic's ordering names the same variant twice
- **THEN** no variant in the group receives a rank

#### Scenario: An ordering naming an unknown variant is refused
- **WHEN** a critic's ordering names an index that is not in the group
- **THEN** no variant in the group receives a rank

### Requirement: A partial fan-out presents what it produced

Where some variants of a group fail, the variants that completed SHALL be
recorded and readable, and the run SHALL be degraded rather than lost.

#### Scenario: Three of five variants still present three
- **WHEN** a fan-out produces some variants and fails on others
- **THEN** the artifacts for the ones that completed exist with their files, and the failure does not remove them

### Requirement: Outcomes are recorded, never inferred

An outcome SHALL be written only when supplied. No outcome SHALL be derived from
a rank, from a run completing, or from any other system state.

#### Scenario: Recording a keep makes the cost view return a number
- **WHEN** an outcome labeled `keep` is recorded against a non-synthetic artifact on a run with recorded cost
- **THEN** `cost_per_accepted_artifact` reports a non-null cost per accepted artifact for that night

#### Scenario: Synthetic outcomes stay out of the cost view
- **WHEN** outcomes are recorded against synthetic artifacts
- **THEN** `cost_per_accepted_artifact` does not count them

#### Scenario: A ranked variant is not thereby accepted
- **WHEN** a variant group is ranked
- **THEN** no outcome exists for any variant in it until one is recorded explicitly

### Requirement: Paths are relative to a configured root

The artifact root SHALL be configurable, and `artifacts.path` SHALL store the
location relative to that root so the same rows are valid under a different
deployment's root.

#### Scenario: A stored path carries no absolute location
- **WHEN** an artifact is recorded
- **THEN** its stored path is relative and contains no filesystem root, home directory or host name

#### Scenario: Two runs on the same night do not collide
- **WHEN** two entries are worked on the same night and each produces an artifact of the same kind
- **THEN** the two files are at different paths and neither overwrites the other
