## Purpose

Guarantee that an idea marked `local-only` never reaches a remote provider, and
make that guarantee auditable after the fact rather than asserted in
documentation.

## Requirements

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
- **WHEN** a `local-only` entry is selected for a run on a profile with no local reasoner
- **THEN** no run is started for that entry, and it is quarantined rather than executed against a remote provider

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

### Requirement: Entries are quarantined when the profile cannot honor their policy

Where the resolved profile cannot honor an entry's policy, the system SHALL
quarantine that entry rather than dispatching it. Quarantined entries MUST NOT
be silently downgraded to a weaker policy, and MUST be surfaced with the
capability finding that caused the quarantine.

Work whose policy the profile can honor MUST continue normally. A degraded
profile reduces what runs, never what is guaranteed.

#### Scenario: Local-only entry on a degraded profile
- **WHEN** the probe finds an incomplete local stack and the profile degrades to `cloud`, and a `local-only` entry is queued
- **THEN** the entry is quarantined, no run is created for it, and the morning brief reports it as blocked naming the probe finding

#### Scenario: Cloud-assisted work continues while quarantine is active
- **WHEN** local-only entries are quarantined on a degraded profile
- **THEN** `cloud-assisted` entries are dispatched and processed normally

#### Scenario: Quarantine clears when capability returns
- **WHEN** a previously unreachable local reasoner becomes available and the profile resolves with local capability
- **THEN** quarantined `local-only` entries become eligible for dispatch without manual re-entry

### Requirement: Local-only availability is a stated capability

Where a resolved profile cannot honor `local-only`, the system SHALL report that
policy as unavailable rather than accepting it and downgrading silently.

#### Scenario: Cloud profile capability report
- **WHEN** the profile resolves to `cloud`
- **THEN** the system reports `local-only` as unavailable, with the reason attributable to the resolved profile

#### Scenario: Unavailable policy is offered as disabled, not omitted
- **WHEN** a capture surface requests the available policies on a profile that cannot honor `local-only`
- **THEN** `local-only` is returned marked unavailable together with its reason, rather than omitted from the list

#### Scenario: Reason is specific to the finding
- **WHEN** `local-only` is unavailable because the local reasoner endpoint is unreachable
- **THEN** the reported reason names that finding, and does not report a generic profile-level message

### Requirement: Context is assembled and filtered locally

Retrieval and context assembly SHALL execute locally on every profile. Only
assembled, policy-filtered context is eligible to leave the machine.

#### Scenario: Cloud-assisted call
- **WHEN** a `cloud-assisted` entry requires a remote completion
- **THEN** retrieval runs locally, redaction is applied before egress, and the model call records that redaction was applied
