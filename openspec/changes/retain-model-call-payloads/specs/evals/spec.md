## MODIFIED Requirements

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

Every recorded result SHALL also point at the retained text that was scored,
where that text was retained. A score is a claim about a specific output, and a
claim nobody can read back is a number on its own authority. This is what makes
a reported improvement checkable by someone who was not there.

#### Scenario: The call is recorded beside the score
- **WHEN** a sample is generated and graded
- **THEN** the recorded result references the model call that produced the output

#### Scenario: A generator that returns only text
- **WHEN** the callable returns a string rather than a recorded completion
- **THEN** scoring is refused, naming the parameter, rather than recording a result whose generator is unknown

#### Scenario: A run's generators are reportable
- **WHEN** a scored run is summarized
- **THEN** the distinct models behind its results are part of the summary

#### Scenario: The scored output is readable afterwards
- **WHEN** a sample is generated, retained and graded
- **THEN** the recorded result points at the retained output, so the text behind the score can be read without reconstructing it

#### Scenario: Retention that did not happen is not invented
- **WHEN** a sample's output was not retained
- **THEN** the result records no pointer rather than a path to a file that is not there
