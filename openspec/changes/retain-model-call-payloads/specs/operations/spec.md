## MODIFIED Requirements

### Requirement: A backup carries the evidence needed to check a restore

Every backup SHALL record what it contains in enough detail to verify a restore
against it: per-table row counts, the schema version, the number and total size
of artifact files, the number and total size of retained payload files, a digest
for each member, and the instant it was taken.

A backup SHALL be verifiable without being restored.

A restore SHALL check what it wrote against that record and fail loudly on any
disagreement, rather than reporting success because nothing raised.

Every tree the backup claims to hold SHALL be counted in the record
individually. A tree that is copied but not counted, or counted but not copied,
is a backup whose claim about itself cannot be checked — which is how the
payload tree came to be absent from both for seven weeks while the tool reported
success.

#### Scenario: A restore is checked rather than assumed
- **WHEN** a restore completes
- **THEN** the restored database's per-table counts and schema version are compared against the record, and a mismatch fails

#### Scenario: A damaged backup is caught before it is needed
- **WHEN** a backup's bytes no longer match its recorded digests
- **THEN** verifying it fails and says which member disagrees

#### Scenario: A record that proves nothing is not enough
- **WHEN** a backup records only the instant it was taken
- **THEN** that is insufficient, because a restore could only be judged by whether it raised

#### Scenario: Retained payloads are counted in the record
- **WHEN** a backup is written from a machine holding retained payload files
- **THEN** the record states how many payload files it holds and their total size, as it does for artifacts

#### Scenario: A restore brings the payloads back
- **WHEN** a backup holding retained payloads is restored
- **THEN** the payload files are written to the configured payload root, and the restore reports how many

### Requirement: A backup never leaves the machine's trust boundary

A backup contains raw unredacted entry text and every recorded prompt and
completion. It SHALL NOT be written to, copied to, or synchronized with any
destination outside the boundary that holds the brain.

The tool SHALL state what an archive contains each time it writes one, so that
the sensitivity of the artifact is present at the moment somebody decides where
to put it.

That statement SHALL be true of the archive it is printed over. A warning about
content the archive does not carry teaches an operator to discount the warning,
which is worse than printing nothing.

#### Scenario: The operator is told what they are holding
- **WHEN** a backup is written
- **THEN** it says the archive contains unredacted captured content and recorded model payloads

#### Scenario: An off-premises destination is proposed
- **WHEN** a destination outside the trust boundary is considered
- **THEN** it is refused, because an export path that includes recorded model payloads is a Privacy Airlock violation

#### Scenario: The warning matches the archive
- **WHEN** the tool warns that an archive holds every recorded model payload
- **THEN** the archive does hold the retained payload files, rather than the warning standing alone
