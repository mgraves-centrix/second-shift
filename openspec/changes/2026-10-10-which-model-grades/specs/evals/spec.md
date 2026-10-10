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
