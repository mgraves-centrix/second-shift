## Purpose

Guarantee that an idea marked `local-only` never reaches a remote provider, and
make that guarantee auditable after the fact rather than asserted in
documentation.

## ADDED Requirements

### Requirement: Policy is resolved per run and recorded with its source

Entry policy SHALL be the default, and each run MUST record the policy it
actually executed under together with why it differs from the default.

A run's effective policy MUST NOT be less restrictive than the entry default
unless the change is attributable to a recorded decision.

#### Scenario: Default carried through
- **WHEN** a run starts for an entry whose default policy is `local-only`
- **THEN** the run records `effective_policy = 'local-only'` and `policy_source = 'entry-default'`

#### Scenario: Explicit upgrade
- **WHEN** the user answers a decision that upgrades an entry to `cloud-assisted`
- **THEN** the subsequent run records `policy_source = 'decision-upgrade'` and the originating decision remains queryable

#### Scenario: Profile cannot honor the policy
- **WHEN** a `local-only` entry is processed on a profile with no local reasoner
- **THEN** the run does not silently execute against a remote provider

### Requirement: Local-only never reaches a remote provider

The system SHALL prevent any model call recorded under `local-only` policy from
naming a remote provider. This MUST be enforced by a database constraint, not
by application-level convention alone.

#### Scenario: Attempted remote call under local-only
- **WHEN** code attempts to record a model call with `policy = 'local-only'` and a remote provider
- **THEN** the write is rejected by the database and the operation fails rather than completing silently

#### Scenario: Local call under local-only
- **WHEN** a model call is recorded with `policy = 'local-only'` and a local provider
- **THEN** the write succeeds

#### Scenario: Auditing an idea after completion
- **WHEN** an entry's artifacts are complete
- **THEN** whether any cloud compute touched that entry is answerable from recorded rows alone

### Requirement: Local-only availability is a stated capability

Where a resolved profile cannot honor `local-only`, the system SHALL report that
policy as unavailable rather than accepting it and downgrading silently.

#### Scenario: Cloud profile capability report
- **WHEN** the profile resolves to `cloud`
- **THEN** the system reports `local-only` as unavailable, with the reason attributable to the resolved profile

### Requirement: Context is assembled and filtered locally

Retrieval and context assembly SHALL execute locally on every profile. Only
assembled, policy-filtered context is eligible to leave the machine.

#### Scenario: Cloud-assisted call
- **WHEN** a `cloud-assisted` entry requires a remote completion
- **THEN** retrieval runs locally, redaction is applied before egress, and the model call records that redaction was applied
