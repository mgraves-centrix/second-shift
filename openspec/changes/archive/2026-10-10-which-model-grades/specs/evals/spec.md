# evals

## MODIFIED Requirements

### Requirement: The judge is configured, not fixed in code

The scoring model SHALL be a configured value. The runner MUST work against any
judge satisfying the interface, and MUST be exercisable without a real model.

Scoring SHALL be reachable as a command, not only as a library call. A scoring
path that exists only where tests call it cannot produce the result the system is
built to report, and its absence is invisible from the command list.

The judge's pinned version SHALL be recorded from configuration rather than from
whatever the endpoint reports about itself, because a version read from the
server floats when the server is restarted against a different checkpoint.

#### Scenario: A stub judge exercises the runner
- **WHEN** the runner executes with a stub judge
- **THEN** results are produced and recorded exactly as with a real one

#### Scenario: No judge configured
- **WHEN** scoring is attempted with no judge configured
- **THEN** it fails clearly, naming what is missing, rather than recording unscored results as scored

#### Scenario: Scoring is reachable from the command line
- **WHEN** the operator lists the eval commands
- **THEN** scoring is among them, and running it against a recorded baseline generates and grades that run

#### Scenario: The pinned version is not the endpoint's word for itself
- **WHEN** a run is scored
- **THEN** the version recorded against it comes from configuration, so restarting the server against another checkpoint cannot change what a past run claims

## ADDED Requirements

### Requirement: An eval answer is produced the way the product produces work

Generation for an eval run SHALL go through the agent invocation path, with the
eval prompt as the task and the brain at the run's pinned commit as the context,
rather than through a composition that exists only for evaluation.

The claim under measurement is that the system gets better at its job. An answer
produced by a harness prompt measures that harness, and an improvement in it
cannot be attributed to the product without a further argument nobody has made.

The agent turn SHALL carry the model call it recorded, so the result row can
name it. A turn whose call cannot be named forces its caller to choose between
an unattributed score and a second lookup that guesses.

#### Scenario: Generation goes through an agent
- **WHEN** an eval run is scored
- **THEN** each answer is produced by an agent invocation against the brain at the run's pinned commit, and the invocation is recorded

#### Scenario: The turn names its model call
- **WHEN** an agent turn completes
- **THEN** the model call it recorded is reachable from the turn, without a second lookup

### Requirement: A prompt edited between two runs is not a brain improvement

The comparison MUST refuse when the two runs' outputs were produced by different
agent prompts. A role prompt is versioned and content-hashed, and a prompt
replaced between week 1 and week 8 moves the scores for a reason that has
nothing to do with memory.

Absence on both sides SHALL compare equal, because generating without an agent
is a legitimate shape; what is refused is a change between the runs rather than
an absence in them.

This SHALL read the prompt through the recorded call rather than from a new
column: a result names its model call, the call names its invocation, the
invocation names its agent, and the agent carries the prompt hash.

#### Scenario: The role prompt changed between the runs
- **WHEN** the two runs' outputs were produced by different agent prompt versions
- **THEN** the comparison is refused and names both, because the difference it would report is the prompt and not the brain

#### Scenario: Neither run used an agent
- **WHEN** neither run's results name an agent invocation
- **THEN** the comparison proceeds, because an absence shared by both sides is not a change between them
