# night-pipeline Specification

## Purpose
The checkpointed walk that turns a captured entry into overnight work: six
stages, each committing its own outcome as it completes, so a late failure never
retracts an early success and the morning always has whatever succeeded. This is
where constitution principle 3 stops being a schema affordance and becomes
behavior.

## Requirements

### Requirement: Each stage commits its own outcome as it completes

Every stage SHALL be recorded independently, in its own transaction, at the
moment it finishes. No stage's outcome SHALL be held pending the completion of
any later stage, and no transaction SHALL span two stages.

#### Scenario: A process killed mid-run leaves completed stages intact
- **WHEN** a night is run and the process is killed after a stage has completed but before the run reaches its last stage
- **THEN** reopening the database shows every stage that completed before the kill recorded as `complete` with its end time, and the stages after it absent or still `running`

#### Scenario: A later failure does not retract an earlier success
- **WHEN** a stage fails after an earlier stage completed
- **THEN** the earlier stage's row still reads `complete` and still carries its end time

### Requirement: Blocking is decided per stage, not by position

A stage SHALL run when the stages its output genuinely depends on have
completed, and SHALL be recorded as `skipped` with a reason otherwise. A stage
SHALL NOT be skipped merely because the stage before it in sequence did not
complete.

#### Scenario: A skipped research stage does not stop mockups or build
- **WHEN** the research stage is skipped and the brief stage completed
- **THEN** the mockups and build stages still run

#### Scenario: Critique is skipped when there is nothing to critique
- **WHEN** the build stage did not complete
- **THEN** the critique stage is recorded as `skipped` with a reason naming the missing input, rather than run

#### Scenario: Nothing downstream runs without a brief
- **WHEN** the brief stage fails
- **THEN** every later stage is recorded as `skipped` and the run's outcome is `failed`

#### Scenario: Distill runs when any stage completed
- **WHEN** at least one stage completed and others failed or were skipped
- **THEN** the distill stage runs

#### Scenario: A skipped stage records why
- **WHEN** any stage is skipped
- **THEN** its reason is recorded and readable without inspecting code

### Requirement: Every run reaches a recorded outcome

`close_run` SHALL be called on every terminal path this process controls, and no
run this process completes SHALL be left with a null outcome or a null end time.

#### Scenario: A fully successful night closes complete
- **WHEN** every stage completes
- **THEN** the run's outcome is `complete` and its end time is set

#### Scenario: A partly successful night closes degraded
- **WHEN** at least one stage completes and at least one fails or is skipped
- **THEN** the run's outcome is `degraded` and its end time is set

#### Scenario: A night where nothing completed closes failed
- **WHEN** no stage completes
- **THEN** the run's outcome is `failed` and its end time is set

#### Scenario: Closing an already-closed run is refused
- **WHEN** a run that has already been closed is closed again
- **THEN** the second close is refused rather than overwriting the recorded outcome

### Requirement: A policy the profile cannot honor quarantines the entry

Where policy resolution is not permitted, the run SHALL NOT be opened. No `runs`
row, no stage row and no model call SHALL be written, the entry SHALL remain
queued, and the reason SHALL be recorded.

#### Scenario: A local-only entry on a profile without local capability is refused
- **WHEN** an entry whose default policy is `local-only` is dispatched on a profile that cannot serve it locally
- **THEN** no run row exists for that entry, no model call is recorded, and the entry is still queued

#### Scenario: The reason for a quarantine is recorded
- **WHEN** an entry is quarantined
- **THEN** a typed failure records the cause, so the entry's absence from the night is explainable

#### Scenario: A quarantined entry is never silently downgraded
- **WHEN** an entry is quarantined for policy
- **THEN** no run exists that recorded a wider effective policy than the entry's default

### Requirement: Dispatching twice does not run an entry twice

Running the pipeline while an entry is already being worked SHALL NOT produce a
second run for that entry.

#### Scenario: A second dispatch finds nothing eligible
- **WHEN** an entry has been dispatched and its status has moved out of `queued`, and the pipeline is dispatched again
- **THEN** no second run is created for that entry

#### Scenario: A failed run returns its entry for another night
- **WHEN** a run fails
- **THEN** its entry is queued again rather than left running or moved to a failed state

### Requirement: A night can be started by hand

The pipeline SHALL be startable from the command line, both for all eligible
entries and for a single named entry, without a scheduler.

#### Scenario: The manual command runs the eligible entries
- **WHEN** the night command is run with no entry named
- **THEN** every eligible entry is dispatched and the outcome of each is reported

#### Scenario: A single entry can be named
- **WHEN** the night command is run naming one entry
- **THEN** only that entry is dispatched

### Requirement: Every stage is attributable

Each stage that runs SHALL open an agent invocation recording the stage and the
agent, and every model call SHALL be recorded with the policy the run resolved
under. A stage that ran SHALL be distinguishable from one that was skipped.

#### Scenario: A stage that ran leaves an invocation naming it
- **WHEN** a stage runs
- **THEN** an agent invocation row exists carrying that stage name

#### Scenario: A skipped stage opens no invocation
- **WHEN** a stage is skipped
- **THEN** no agent invocation exists for that stage, so the two states are distinguishable in the data

#### Scenario: Model calls record the run's resolved policy
- **WHEN** a stage makes a model call
- **THEN** the recorded call carries the policy the run resolved under, not the entry's default
