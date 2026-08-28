## Purpose

The measurement spine: a fixed prompt set run against a pinned judge and rubric,
sampled for variance, and attributed to the exact brain state that produced each
output.

## ADDED Requirements

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
