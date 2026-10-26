## ADDED Requirements

### Requirement: What a model call said is retained, not only what it cost

For every completion, the system SHALL retain the prompt it was given and the
text it produced, and SHALL record a row referencing both beside the call's cost
row. A token count cannot be reconstructed into a prompt, so a completion that
runs before retention exists is permanently unreadable and permanently
untrainable. (ADR 0007)

Retention MUST be performed by the provider base class, not by individual
implementations, for the same reason recording a `model_calls` row is: an
implementation cannot forget instrumentation it never writes.

The retained text SHALL live on disk, referenced by a path relative to a
configured root, and MUST NOT be stored in the database. Contexts run to a
million tokens, and the stored path MUST NOT be absolute, because an absolute
path pins one machine's directory layout into data another deployment reads.

The recorded byte counts SHALL describe the files as read back after writing,
not the text that was passed in. A count derived from the intent proves what was
meant rather than what landed, and a truncated write or a full disk then
produces a row that is confidently wrong about a file nobody has checked.

#### Scenario: A completion is retained
- **WHEN** a reasoner returns a completion
- **THEN** the prompt and the completion text are readable from disk afterwards, and a payload row references both, linked to that call's recorded id

#### Scenario: An implementation cannot skip retention
- **WHEN** a new provider implementation is added that overrides only its internal completion method
- **THEN** its completions are retained without that implementation containing any retention code

#### Scenario: The database holds pointers, not text
- **WHEN** a payload row is read
- **THEN** it carries paths relative to the configured root and byte counts, and neither the prompt nor the completion text is present in any column

### Requirement: Retained content carries whether it may be trained on

A retained payload SHALL record whether it is eligible to enter a training set,
and synthetic content MUST NOT be eligible. Development and seed data that
could reach a training set is the same contamination `is_synthetic` exists to
prevent, one table further on.

A retained payload SHALL record whether the text it holds had passed through a
redaction step, so that a reader can tell raw captured content from what was
prepared for egress.

#### Scenario: Synthetic content is never trainable
- **WHEN** a completion recorded as synthetic is retained
- **THEN** its payload is marked ineligible for training

#### Scenario: Redaction is recorded, not inferred
- **WHEN** a completion whose prompt passed through redaction is retained
- **THEN** its payload is marked redacted, and one that did not is not

### Requirement: Losing evidence does not lose the night

A failure to retain a payload SHALL be recorded as a typed failure and SHALL
NOT fail the completion or prevent the cost row from being recorded. The
completion is the product and the payload is evidence about it; a full disk at
2am must cost the evidence and nothing else.

A retention failure MUST NOT be silent. No payload row SHALL be written for a
file that is not there, because a row pointing at a missing file records a
provenance nobody can check — the same defect as recording none while looking
like it did.

#### Scenario: The disk refuses the write
- **WHEN** retaining a payload fails
- **THEN** the caller still receives the completion, the `model_calls` row still exists, a typed failure is recorded, and no payload row references the file that was not written

#### Scenario: A night is not lost to its own evidence
- **WHEN** a stage's completion cannot be retained
- **THEN** the stage continues, because the failure is recorded rather than raised
