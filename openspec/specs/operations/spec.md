# operations Specification

## Purpose
The machine, and what happens when it is gone. It holds the only copy of every
captured idea, the week-1 eval baseline and the rubric hash that pins it, and a
baseline lost cannot be re-taken later and made to mean the same thing. So a
copy is taken through the one mechanism demonstrated correct while something is
writing — never by copying a file whose committed transactions are still in its
write-ahead log — and it carries the evidence a restore is checked against
rather than being judged by whether it crashed. Destructive steps refuse by
default and say what they are protecting. A backup is a complete second copy of
unredacted content, so it never leaves the boundary that holds the brain
(ADR 0014). And the procedure records, per step, whether anybody has actually
run it: a recovery document nobody has followed is a hypothesis, and one where
some steps run on every gate while others have never been executed is two
documents pretending to be one.

## Requirements

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

### Requirement: A backup is taken every night, after the night has run

A backup SHALL be taken once per night, ordered after the night pipeline rather
than at a clock time chosen to be later than it.

It SHALL be taken whether or not that night succeeded, because a night that went
wrong is the one most worth holding a copy of.

Its destination SHALL come from configuration held outside this repository, and
a missing configuration MUST fail the attempt loudly rather than start a backup
with nowhere to put it.

Where nights stop running, backups stop with them. That coupling is deliberate:
a machine that has stopped doing the work is a machine whose backups have
nothing new to hold, and the staleness check is what makes the silence visible.

#### Scenario: The night finishes
- **WHEN** the night pipeline finishes
- **THEN** a backup is taken, ordered after it rather than concurrently with it

#### Scenario: The night failed
- **WHEN** the night pipeline exits with a failure
- **THEN** a backup is still taken

#### Scenario: No destination is configured
- **WHEN** the scheduled backup runs on a machine with no destination configured
- **THEN** it fails and says so, rather than succeeding against a default

### Requirement: A backup refuses to be written to the disk it exists to survive

A backup SHALL refuse a destination on the same storage device as the database,
unless the operator explicitly asks for that.

The refusal MUST name the way out, because a deliberate local rehearsal is a
real use and an obstruction that does not say how to proceed is one somebody
routes around.

Where a backup has already been written to the same device as the database, that
SHALL be reported by the check that reports whether the machine is well, rather
than left to be discovered.

#### Scenario: A network destination is not mounted
- **WHEN** a backup is written to a mount point whose filesystem is not mounted, so it lands on the local disk
- **THEN** it is refused, because every such backup would succeed while being worthless for the failure it exists for

#### Scenario: A deliberate local rehearsal
- **WHEN** an operator asks for a backup onto the same device on purpose
- **THEN** it proceeds, because rehearsing the procedure is how it stops being a hypothesis

#### Scenario: Backups have been landing locally for weeks
- **WHEN** the newest backup sits on the same device as the database
- **THEN** the machine is reported as not well, naming that as the reason

### Requirement: Whether a night is in flight is answerable before anything is restarted

There SHALL be a command that reports whether a night is currently running
against the configured database, and whose exit status distinguishes the two
states so that it can gate another command.

The state MUST be read from the lock a running night holds, not from a run left
open in the database. An open run is also what a night killed last week leaves
behind, and restarting a service on that evidence would refuse forever.

It SHALL use the same exit code for "a night is already running" as the night
itself uses, so the two cannot drift into different answers for one state.

The check that reports whether the machine is well SHALL report the same state,
because a night in flight bears on a deploy, a restart and a reboot alike — and
a night in flight is not a fault.

#### Scenario: A service is about to be restarted
- **WHEN** an operator gates a restart on this command
- **THEN** the restart does not proceed while a night is running, because restarting the reasoner mid-night costs that night its morning

#### Scenario: A night died without closing its run
- **WHEN** a previous night was killed and left a run open
- **THEN** the machine reports idle, because the kernel released the lock when the process exited and the open run is the next night's recovery to perform

#### Scenario: A deployment that never runs nights
- **WHEN** the command runs where no night has ever run
- **THEN** it reports idle rather than failing, because a machine with no lock file is a machine with no night in flight

#### Scenario: The machine is well and busy
- **WHEN** the health check runs while a night is in flight
- **THEN** it reports the night and does not count it as a fault
