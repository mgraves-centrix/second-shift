# evals

## ADDED Requirements

### Requirement: Two runs are compared only when the comparison would mean something

There SHALL be a command that compares two recorded eval runs and reports the
difference in their scores.

It MUST refuse the comparison, rather than warn, when any of the following
holds, because each makes the reported number mean something other than what it
appears to mean:

- the two runs pin different rubrics;
- the two runs pin the same brain state, so nothing under test has changed;
- either run is incomplete, because a partial run is not comparable to a whole one;
- the two runs were graded by different judges;
- either run is synthetic.

Every difference it reports SHALL be accompanied by the spread of both runs. A
difference smaller than the wider spread MUST NOT be presented as a change.

It SHALL report each rubric dimension separately as well as overall, because an
overall mean can be carried by one dimension moving while another regresses.

#### Scenario: The brain did not change
- **WHEN** both runs pin the same brain state
- **THEN** the comparison is refused and says so plainly, rather than reporting a number that measures sampling noise

#### Scenario: The rubric changed between the runs
- **WHEN** the two runs pin different rubrics
- **THEN** the comparison is refused, because a rubric is pinned to a measurement precisely so that this cannot be done silently

#### Scenario: One run did not finish
- **WHEN** either run has a failed sample
- **THEN** the comparison is refused, because averaging over what survived hides which prompts did not

#### Scenario: A difference inside the noise
- **WHEN** the difference between the two means is smaller than the wider of the two spreads
- **THEN** it is reported as not shown to have moved, rather than as an improvement

#### Scenario: One dimension carries the mean
- **WHEN** the overall mean improves while a dimension regresses
- **THEN** both are visible, because the dimension is the finding and the mean is the headline

#### Scenario: A generated run is not evidence
- **WHEN** either run is synthetic
- **THEN** the comparison is refused and says which, rather than returning an empty report
