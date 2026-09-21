# operations

## ADDED Requirements

### Requirement: A backup is a copy that was taken correctly, not a copy of the files

The database SHALL be copied through a mechanism that produces a consistent
snapshot while another process may be writing to it.

Copying the database file alone MUST NOT be used, because the database runs in
write-ahead logging mode and committed transactions — including the schema
itself — may live outside that file at any moment.

A backup SHALL contain the database and the artifacts the night has written. It
SHALL NOT contain the brain, which is a git repository with its own mirror, and
the exclusion MUST be stated in the backup's own record rather than left to be
inferred.

#### Scenario: A backup is taken while something is writing
- **WHEN** a backup runs while another connection holds an open write transaction
- **THEN** the backup contains every committed row and none of the uncommitted ones

#### Scenario: The naive copy is demonstrably wrong
- **WHEN** the database file is copied on its own, without its write-ahead log
- **THEN** the copy is missing committed data, which is why the mechanism above is required rather than preferred

#### Scenario: An operator reads what was excluded
- **WHEN** an operator inspects a backup's record
- **THEN** the brain is named as excluded with the reason, so nobody concludes from silence that it was included

### Requirement: A backup carries the evidence needed to check a restore

Every backup SHALL record what it contains in enough detail to verify a restore
against it: per-table row counts, the schema version, the number and total size
of artifact files, a digest for each member, and the instant it was taken.

A backup SHALL be verifiable without being restored.

A restore SHALL check what it wrote against that record and fail loudly on any
disagreement, rather than reporting success because nothing raised.

#### Scenario: A restore is checked rather than assumed
- **WHEN** a restore completes
- **THEN** the restored database's per-table counts and schema version are compared against the record, and a mismatch fails

#### Scenario: A damaged backup is caught before it is needed
- **WHEN** a backup's bytes no longer match its recorded digests
- **THEN** verifying it fails and says which member disagrees

#### Scenario: A record that proves nothing is not enough
- **WHEN** a backup records only the instant it was taken
- **THEN** that is insufficient, because a restore could only be judged by whether it raised

### Requirement: A destructive operation refuses by default

Restoring over an existing database MUST be refused unless the operator
explicitly asks for the overwrite, and the refusal MUST say what is already
there.

Taking a backup SHALL require the operator to name the destination. There is no
default destination, because a default is how a copy of every captured idea ends
up somewhere nobody chose.

#### Scenario: A restore would overwrite live data
- **WHEN** a restore targets a path that already holds a database
- **THEN** it refuses, names what is there, and says how to proceed deliberately

#### Scenario: A backup is asked for with no destination
- **WHEN** a backup is requested without a destination
- **THEN** it refuses rather than choosing one

### Requirement: A backup never leaves the machine's trust boundary

A backup contains raw unredacted entry text and every recorded prompt and
completion. It SHALL NOT be written to, copied to, or synchronized with any
destination outside the boundary that holds the brain.

The tool SHALL state what an archive contains each time it writes one, so that
the sensitivity of the artifact is present at the moment somebody decides where
to put it.

#### Scenario: The operator is told what they are holding
- **WHEN** a backup is written
- **THEN** it says the archive contains unredacted captured content and recorded model payloads

#### Scenario: An off-premises destination is proposed
- **WHEN** a destination outside the trust boundary is considered
- **THEN** it is refused, because an export path that includes recorded model payloads is a Privacy Airlock violation

### Requirement: One command reports whether the machine is well

There SHALL be a single command that checks the deployed machine and exits
non-zero when any check fails.

It SHALL report every check rather than stopping at the first failure.

It SHALL check that the configuration resolves, that the database opens with the
expected journal mode and a current schema, that the data directory belongs to
the account running it, that the local reasoner answers on the configured port
serving the expected name, and how old the newest backup is.

It MUST NOT become a service, a daemon, or anything that emits to a destination:
the telemetry database is the monitoring.

#### Scenario: Several things are wrong at once
- **WHEN** more than one check fails
- **THEN** all of them are reported in one run, because fixing one and re-running for the next is work the first run could have saved

#### Scenario: The service runs as the wrong account
- **WHEN** the resolved data directory is not under the home of the account running the check
- **THEN** it is reported, because that misconfiguration has corrupted the write-ahead log before

#### Scenario: Backups stopped without anyone noticing
- **WHEN** the newest backup is older than the checked interval
- **THEN** it is reported, because a schedule that silently stopped looks exactly like one that was never set up

#### Scenario: Every check can fail
- **WHEN** the condition a check exists for is broken
- **THEN** that check reports a failure, because a check that cannot go red reads as evidence while proving nothing

### Requirement: A recovery procedure states which of its steps have been executed

The recovery procedure SHALL record, per step, whether it has been executed and
against what.

A step that has only been executed against test data MUST NOT be presented as
executed against the machine's data.

Steps that remain unexecuted SHALL be listed where the project tracks
outstanding work, not only inside the procedure.

#### Scenario: A reader judges how much to trust a step
- **WHEN** an operator reads the procedure under pressure
- **THEN** each step says whether anyone has done it, so the untried steps are the ones read carefully

#### Scenario: An unexecuted step is not lost in the document
- **WHEN** a step cannot be executed yet
- **THEN** it appears in the project's outstanding work as well, because an obligation recorded only in the document that assumes it is a dropped one
