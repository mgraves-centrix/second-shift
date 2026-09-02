## Purpose

The measurement spine: a fixed prompt set run against a pinned judge and rubric,
sampled for variance, and attributed to the exact brain state that produced each
output.

## Requirements

### Requirement: A run is sampled, not measured once

Each active prompt SHALL be run several times within an eval run, and results
reported with a central value and a spread.

A single sample per prompt MUST NOT be presented as a measurement.

#### Scenario: Repeated sampling
- **WHEN** an eval run executes with three samples configured
- **THEN** each active prompt produces three recorded results, distinguished by sample index

#### Scenario: Variance is reportable
- **WHEN** results for a prompt are summarized
- **THEN** both a central value and a spread are available, so a difference between runs can be distinguished from sampling noise

### Requirement: The judge and rubric are pinned per run

An eval run SHALL record the judge model, its version, and the hash of the rubric
used. These MUST be recorded at the time of the run.

#### Scenario: Pinning is recorded
- **WHEN** an eval run completes
- **THEN** the judge model, its version and the rubric hash are recorded against that run

#### Scenario: A changed rubric does not silently compare
- **WHEN** the rubric changes and a new run executes
- **THEN** the new run records a different rubric hash, so results under different rubrics are distinguishable rather than plotted together

### Requirement: Scoring is attributed to a recorded brain state

An eval run SHALL record the brain commit it ran against. When scoring happens
separately from generation, it MUST be attributed to the brain commit recorded at
generation, never to the current one.

#### Scenario: Baseline inputs recorded before a judge exists
- **WHEN** a baseline is recorded while no model is available to score it
- **THEN** the prompts, the rubric hash and the brain commit are recorded, and the run is marked as awaiting scoring

#### Scenario: Later scoring uses the recorded state
- **WHEN** an awaiting-scoring run is scored days later, after the brain has changed
- **THEN** the results are attributed to the brain commit recorded at baseline, not to the brain's current commit

#### Scenario: Generation reads the brain at the recorded commit
- **WHEN** an awaiting-scoring run is generated and scored after the brain has changed
- **THEN** the brain content used is what that commit holds, not what the working tree currently holds — otherwise the pinning records a state the output was never produced from

#### Scenario: The recorded state is not overwritten by scoring
- **WHEN** scoring completes for a previously recorded run
- **THEN** the run's brain commit is unchanged

### Requirement: The judge is configured, not fixed in code

The scoring model SHALL be a configured value. The runner MUST work against any
judge satisfying the interface, and MUST be exercisable without a real model.

#### Scenario: A stub judge exercises the runner
- **WHEN** the runner executes with a stub judge
- **THEN** results are produced and recorded exactly as with a real one

#### Scenario: No judge configured
- **WHEN** scoring is attempted with no judge configured
- **THEN** it fails clearly, naming what is missing, rather than recording unscored results as scored

### Requirement: Scores are structured, not parsed from prose

The judge SHALL return a score per rubric dimension as structured data. Scores
MUST NOT be extracted by parsing free text.

#### Scenario: Structured scores are recorded
- **WHEN** a judge scores an output
- **THEN** a value per rubric dimension is recorded, along with the total

#### Scenario: An unparseable judgement is a failure, not a zero
- **WHEN** a judge returns something that is not a valid set of scores
- **THEN** a typed failure is recorded and no score is written, because a zero would be indistinguishable from a genuinely poor answer

### Requirement: A partial run is recorded as partial

Where some samples succeed and others fail, the successful results SHALL be
recorded and the run marked incomplete.

#### Scenario: Some samples fail
- **WHEN** one sample of three fails while the others succeed
- **THEN** the two successful results are recorded, a typed failure is recorded for the third, and the run is identifiable as incomplete

#### Scenario: An incomplete run is not silently comparable
- **WHEN** an incomplete run is summarized
- **THEN** its incompleteness is evident, so it is not compared against a complete run as though equivalent

### Requirement: Prompts and rubric are content, loaded from files

Prompts and the rubric SHALL be loaded from files rather than embedded in code,
and prompts carry an active flag so a candidate set can be narrowed by selection
rather than deletion.

#### Scenario: Only active prompts run
- **WHEN** an eval run executes with some prompts marked inactive
- **THEN** only the active ones are run

#### Scenario: Selection does not lose the candidates
- **WHEN** prompts are narrowed to a chosen subset
- **THEN** the unselected candidates remain recorded rather than deleted

#### Scenario: The rubric hash follows its content
- **WHEN** the rubric file changes
- **THEN** the hash recorded by the next run differs

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
