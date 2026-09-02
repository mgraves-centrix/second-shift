## ADDED Requirements

### Requirement: Remote work rejoins the invocation tree under its dispatcher

Telemetry reported by out-of-process work SHALL be attached beneath the
invocation that dispatched it, at the depth that position implies.

Work whose dispatching invocation is unknown MUST NOT be recorded. Remote work
MUST NOT appear as an opaque span.

#### Scenario: A job's work joins the tree
- **WHEN** a dispatched job reports its invocations and model calls
- **THEN** they appear beneath the dispatching invocation, at full depth, indistinguishable in shape from work done in process

#### Scenario: An unknown dispatcher is refused
- **WHEN** a report names a dispatching invocation that does not exist
- **THEN** nothing is written, because a row attached to nothing is worse than a row missing

#### Scenario: A partial batch does not half-write
- **WHEN** a report names a parent that has not itself been recorded
- **THEN** the report is refused rather than partially applied

### Requirement: Reported telemetry is authenticated and not counted twice

The channel carrying telemetry from out-of-process work SHALL authenticate every
report. A report that cannot be authenticated MUST be refused, and MUST NOT be
recorded.

The same work reported more than once — by a retry, a redelivery, or a job that
reports before and after being restarted — MUST NOT be recorded more than once.
Deduplication SHALL be enforced by the recorder rather than trusted to the
reporter.

#### Scenario: An unauthenticated report is refused
- **WHEN** a report arrives without valid authentication
- **THEN** it is refused and nothing is written

#### Scenario: The same work reported twice
- **WHEN** a job's telemetry is delivered a second time
- **THEN** the second delivery adds no rows, because duplicated rows inflate the cost curve and the token comparison silently

#### Scenario: Deduplication does not depend on the reporter
- **WHEN** a reporter sends work it has already sent, without marking it as a repeat
- **THEN** it is still not counted twice

### Requirement: Ingest serializes through the single writer

Telemetry arriving from out-of-process work SHALL be written through the same
recorder, under the same lock, as work recorded in process.

It MUST NOT open a second connection to the database.

#### Scenario: Ingest and local work write concurrently
- **WHEN** a report arrives while the orchestrator is writing its own telemetry
- **THEN** both are serialized through the one writer rather than contending as two

### Requirement: A dispatched job is accounted for, or the run is visibly incomplete

Every dispatched job SHALL either have its telemetry recorded, or leave the run
identifiable as incomplete.

A job whose cost is unknown MUST NOT be presented as a job that cost nothing.

#### Scenario: A job reports
- **WHEN** a dispatched job completes and reports
- **THEN** its model calls carry their costs and appear in the same accounting as local work

#### Scenario: A job never reports
- **WHEN** a dispatched job produces no telemetry
- **THEN** the run is identifiable as incomplete, rather than showing a fan-out that appears to have been free

### Requirement: A failed job does not lose the run

A job that fails, times out, or never returns SHALL be reported as a failed
result and recorded as a typed failure.

It MUST NOT abort the run or discard the output of stages that already
completed.

#### Scenario: A build variant fails
- **WHEN** one dispatched variant fails while others succeed
- **THEN** the successful variants remain, the failure is recorded, and the run continues

#### Scenario: A job never returns
- **WHEN** polling a job exceeds its deadline
- **THEN** a typed failure is recorded and the run proceeds with what it has, because a morning that shows less is correct and a morning that shows nothing is not

### Requirement: Local-only work is never dispatched off the machine

Work carrying `local-only` SHALL NOT be dispatched to a remote executor or sent
to a remote reasoner.

This MUST be enforced at the call and remain unrecordable at the database. The
enforcement MUST NOT be weakened, made conditional, or bypassable by
configuration.

#### Scenario: A local-only idea reaches the executor
- **WHEN** dispatch is attempted for work under `local-only`
- **THEN** it is refused before anything leaves the process

#### Scenario: The database still refuses it
- **WHEN** a caller bypasses the guard and attempts to record a remote call under `local-only`
- **THEN** the write fails

#### Scenario: Only assembled context leaves
- **WHEN** a `cloud-assisted` job is dispatched
- **THEN** it carries assembled, policy-filtered context and never the brain

### Requirement: The judge instance is this code, with no real data

The judge instance SHALL run the same code as the personal instance, separated
only by compute profile.

It MUST contain zero real data, MUST be labeled in-UI as a demo, and every row it
holds MUST be marked synthetic so it can never contaminate a measurement.

#### Scenario: The same code
- **WHEN** the judge instance runs
- **THEN** it differs from the personal instance by compute profile alone, with no demo-only branch in business logic

#### Scenario: Its data is excluded from measurement
- **WHEN** a rollup or an eval reads the tables
- **THEN** the judge instance's rows are excluded, because they are marked synthetic

#### Scenario: A viewer is told what they are looking at
- **WHEN** the judge instance is opened
- **THEN** it says it is a demo
