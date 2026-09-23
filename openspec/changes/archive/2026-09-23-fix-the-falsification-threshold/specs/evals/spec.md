# evals

## ADDED Requirements

### Requirement: What would falsify the claim is fixed before the result exists

The difference that counts as an improvement SHALL be recorded before the second
run is scored, in a file whose content is hashed.

The comparison SHALL report that hash alongside its verdict, so that a threshold
edited after the result is visible wherever the result is read.

A comparison that does not meet the recorded bar SHALL be reported as no
improvement having been shown, which is not the same statement as the claim
having been disproved, and the distinction MUST be preserved in what is
reported.

Where the bar is met in the opposite direction, that SHALL be reported with the
same prominence as the favorable result.

#### Scenario: The threshold predates the number
- **WHEN** a reader asks whether the bar was chosen after seeing the result
- **THEN** the date it was fixed and the hash of the text are both in the comparison's own output, and the file's addition is in the history

#### Scenario: The bar is not met
- **WHEN** the difference does not clear the recorded bar
- **THEN** it is reported as no improvement shown, rather than as the brain having learned nothing

#### Scenario: The result goes the other way
- **WHEN** the bar is met in the direction of a regression
- **THEN** it is reported as a regression rather than withheld

#### Scenario: The threshold is edited afterwards
- **WHEN** the recorded text changes
- **THEN** the hash printed beside the verdict changes with it

## MODIFIED Requirements

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
- either run is synthetic;
- the two runs were scored over different sets of prompts.

Every difference it reports SHALL be accompanied by the spread of both runs. A
difference smaller than the wider spread MUST NOT be presented as a change.

It SHALL report each rubric dimension separately as well as overall, because an
overall mean can be carried by one dimension moving while another regresses.

The unit of comparison SHALL be one prompt's mean rather than one sample, paired
across the two runs. Prompts differ from one another systematically, so an
estimate pooled over every sample mixes the variation between prompts into one
meant to describe the variation within them.

#### Scenario: The brain did not change
- **WHEN** both runs pin the same brain state
- **THEN** the comparison is refused and says so plainly, rather than reporting a number that measures sampling noise

#### Scenario: The rubric changed between the runs
- **WHEN** the two runs pin different rubrics
- **THEN** the comparison is refused, because a rubric is pinned to a measurement precisely so that this cannot be done silently

#### Scenario: The prompt set changed between the runs
- **WHEN** the two runs were scored over different prompts
- **THEN** the comparison is refused, because there is no pairing across two different sets and the alternative is comparing two different questions

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
