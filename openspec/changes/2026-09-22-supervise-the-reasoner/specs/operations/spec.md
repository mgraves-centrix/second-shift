# operations

## ADDED Requirements

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
