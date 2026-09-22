# operations

## ADDED Requirements

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
