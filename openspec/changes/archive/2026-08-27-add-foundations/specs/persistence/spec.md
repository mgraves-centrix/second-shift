## Purpose

Durable, append-only storage for every entity in the system, with forward-only
migrations and a hard separation between real data and the synthetic data used
for development, seeding and the judge instance.

## ADDED Requirements

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

#### Scenario: Recording a failure recurrence
- **WHEN** the same failure signature is recorded three times
- **THEN** three rows exist in `failures` and the `failure_ledger` view reports a recurrence count of 3

#### Scenario: No generic mutation
- **WHEN** application code attempts to modify a recorded `model_calls` row
- **THEN** no repository method exists to do so

### Requirement: Synthetic data isolation

Every table that accumulates evidence SHALL carry an `is_synthetic` flag. Every
rollup view used for measurement MUST exclude synthetic rows.

#### Scenario: Synthetic rows excluded from measurement
- **WHEN** a synthetic night writes runs, model calls and artifacts with `is_synthetic = 1`
- **THEN** the `run_cost`, `night_totals` and `cost_per_accepted_artifact` views return no data attributable to those rows

#### Scenario: Synthetic rows remain renderable
- **WHEN** the night view requests events for a synthetic run
- **THEN** those events are returned, so the scrubber and the judge instance can render seeded data
