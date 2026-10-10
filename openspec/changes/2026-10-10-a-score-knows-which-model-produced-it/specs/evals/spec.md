# evals

## ADDED Requirements

### Requirement: A score records the model call that produced what was scored

Every recorded result SHALL reference the model call whose output the judge
graded. The generator is not inferable afterwards: two runs over the same
prompts, the same rubric and the same brain state are distinguishable only by
what produced their text, and a score with no reference to its call is a number
whose subject is unknown.

The callable that produces an output SHALL return the recorded call, not its
text alone. A callable returning text alone MUST be refused, naming the
parameter, rather than coerced — coercing it would restore the unrecorded case
without saying so, which is the state this requirement exists to end.

A run's distinct generating models SHALL be reportable from its summary, so the
question "what produced this run" is answerable without writing SQL against a
database on another machine.

#### Scenario: The call is recorded beside the score
- **WHEN** a sample is generated and graded
- **THEN** the recorded result references the model call that produced the output

#### Scenario: A generator that returns only text
- **WHEN** the callable returns a string rather than a recorded completion
- **THEN** scoring is refused, naming the parameter, rather than recording a result whose generator is unknown

#### Scenario: A run's generators are reportable
- **WHEN** a scored run is summarized
- **THEN** the distinct models behind its results are part of the summary

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
- the two runs were scored over different sets of prompts;
- either run does not record which model produced its outputs, because a guard
  that cannot see one side of the comparison is not a guard;
- the two runs' outputs were produced by different models, because then the
  difference is the model rather than the brain, and the brain is what the
  measurement is about.

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

#### Scenario: The model changed between the runs
- **WHEN** the two runs' outputs were produced by different models
- **THEN** the comparison is refused and names both models, because the difference it would report is the model and not the brain

#### Scenario: One run's generator is unrecorded
- **WHEN** either run has results that reference no model call
- **THEN** the comparison is refused, because the comparison cannot be shown to be between two states of one system rather than two systems

### Requirement: The judge is configured, not fixed in code

The scoring model SHALL be a configured value. The runner MUST work against any
judge satisfying the interface, and MUST be exercisable without a real model.

Scoring SHALL be reachable as a command, not only as a library call. A scoring
path that exists only where tests call it cannot produce the result the system is
built to report, and its absence is invisible from the command list.

#### Scenario: A stub judge exercises the runner
- **WHEN** the runner executes with a stub judge
- **THEN** results are produced and recorded exactly as with a real one

#### Scenario: No judge configured
- **WHEN** scoring is attempted with no judge configured
- **THEN** it fails clearly, naming what is missing, rather than recording unscored results as scored

#### Scenario: Scoring is reachable from the command line
- **WHEN** the operator lists the eval commands
- **THEN** scoring is among them, and running it with no judge configured exits non-zero naming what is missing
