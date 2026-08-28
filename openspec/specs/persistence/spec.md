## Purpose

Durable, append-only storage for every entity in the system, with forward-only
migrations and a hard separation between real data and the synthetic data used
for development, seeding and the judge instance.

## Requirements

### Requirement: Schema application and migration

The system SHALL apply database migrations forward-only from numbered SQL files,
tracking applied versions in a `schema_version` table. Migrations MUST be
idempotent at the file level: applying an already-applied version is a no-op,
not an error.

#### Scenario: Fresh database
- **WHEN** the application starts against a database file that does not exist
- **THEN** the database is created, every migration is applied in numeric order, and `schema_version` records the highest applied version

#### Scenario: Already current
- **WHEN** the application starts against a database at the latest version
- **THEN** no migration is applied and startup proceeds without error

#### Scenario: Partially migrated
- **WHEN** the application starts against a database at version 3 with migrations up to 5 available
- **THEN** migrations 4 and 5 are applied in order, and migrations 1 through 3 are not re-applied

### Requirement: Append-only data access

The repository layer SHALL expose insertion and a closed set of named completion
operations. It MUST NOT expose a generic update or delete for any append-only
table.

Values that behave as counters MUST be derived through views rather than stored
and mutated.

Where an entity legitimately changes state after insertion — an entry moving
through its lifecycle, a transcript arriving after the row it belongs to — that
change SHALL be a named operation with its own preconditions. A generic
`update_entry(**fields)` is not permitted.

#### Scenario: Recording a failure recurrence
- **WHEN** the same failure signature is recorded three times
- **THEN** three rows exist in `failures` and the `failure_ledger` view reports a recurrence count of 3

#### Scenario: No generic mutation
- **WHEN** application code attempts to modify a recorded `model_calls` row
- **THEN** no repository method exists to do so

#### Scenario: Entry lifecycle transitions are named
- **WHEN** an entry moves from one status to another
- **THEN** the change is made through a named operation for that transition, which refuses a transition that is not permitted from the current status

### Requirement: Synthetic data isolation

Every table that accumulates evidence SHALL carry an `is_synthetic` flag. Every
rollup view used for measurement MUST exclude synthetic rows.

Any query that selects work for execution MUST also exclude synthetic rows.
Development and seed data must never be *acted upon*, not merely never counted.

#### Scenario: Synthetic rows excluded from measurement
- **WHEN** a synthetic night writes runs, model calls and artifacts with `is_synthetic = 1`
- **THEN** the `run_cost`, `night_totals` and `cost_per_accepted_artifact` views return no data attributable to those rows

#### Scenario: Synthetic rows remain renderable
- **WHEN** the night view requests events for a synthetic run
- **THEN** those events are returned, so the scrubber and the judge instance can render seeded data

#### Scenario: Synthetic entries are never selected for execution
- **WHEN** synthetic entries exist in a queued state alongside real ones
- **THEN** the query that selects entries for dispatch returns only the real ones

### Requirement: Concurrent writes are serialized

All writes to the database SHALL be serialized through a single lock. Because
the connection's own cross-thread guard is deliberately disabled, no component
may write outside that lock.

Any repository primitive that does not take the lock MUST say so, and MUST NOT
be called from a request handler or from concurrent work.

#### Scenario: Capture concurrent with night work
- **WHEN** an entry is captured while the orchestrator is writing
- **THEN** both writes serialize through the same lock rather than interleaving on the shared connection

#### Scenario: Unlocked primitives are marked
- **WHEN** a repository method writes without taking the lock
- **THEN** its documentation states that it is unsafe for concurrent use and names the safe alternative
