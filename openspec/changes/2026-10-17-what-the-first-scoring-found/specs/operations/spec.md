# operations

## MODIFIED Requirements

### Requirement: A backup is a copy that was taken correctly, not a copy of the files

The database SHALL be copied through a mechanism that produces a consistent
snapshot while another process may be writing to it.

Copying the database file alone MUST NOT be used, because the database runs in
write-ahead logging mode and committed transactions — including the schema
itself — may live outside that file at any moment.

A backup SHALL contain the database, the artifacts the night has written, and
every model call's kept prompt and completion. It SHALL NOT contain the brain,
which is a git repository with its own mirror, and the exclusion MUST be stated
in the backup's own record rather than left to be inferred.

Where the payloads are MUST be named by the caller, with no default. A backup
that silently omitted them would lose the one part of the data that cannot be
reconstructed while printing that it holds it.

#### Scenario: A backup is taken while something is writing
- **WHEN** a backup runs while another connection holds an open write transaction
- **THEN** the backup contains every committed row and none of the uncommitted ones

#### Scenario: The naive copy is demonstrably wrong
- **WHEN** the database file is copied on its own, without its write-ahead log
- **THEN** the copy is missing committed data, which is why the mechanism above is required rather than preferred

#### Scenario: An operator reads what was excluded
- **WHEN** an operator inspects a backup's record
- **THEN** the brain is named as excluded with the reason, so nobody concludes from silence that it was included

#### Scenario: The payloads travel with the database
- **WHEN** a backup is taken on a machine that has kept model call payloads
- **THEN** every payload file is a member of the backup, and a restore puts them back beside the database whose rows reference them

### Requirement: A backup carries the evidence needed to check a restore

Every backup SHALL record what it contains in enough detail to verify a restore
against it: per-table row counts, the schema version, the number and total size
of artifact files, the number and total size of payload files, a digest for
each member, and the instant it was taken.

A backup SHALL be verifiable without being restored.

A restore SHALL check what it wrote against that record and fail loudly on any
disagreement, rather than reporting success because nothing raised.

A record written before payloads were backed up carries no payload counts. It
SHALL verify and restore as an older backup, not be refused as a damaged one.

#### Scenario: A restore is checked rather than assumed
- **WHEN** a restore completes
- **THEN** the restored database's per-table counts and schema version are compared against the record, and a mismatch fails

#### Scenario: A damaged backup is caught before it is needed
- **WHEN** a backup's bytes no longer match its recorded digests
- **THEN** verifying it fails and says which member disagrees

#### Scenario: A record that proves nothing is not enough
- **WHEN** a backup records only the instant it was taken
- **THEN** that is insufficient, because a restore could only be judged by whether it raised

#### Scenario: A backup from before payloads were kept
- **WHEN** a backup whose record has no payload counts is verified and restored
- **THEN** both succeed, and the restore reports no payload files
