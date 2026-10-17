# telemetry

## ADDED Requirements

### Requirement: Every model call keeps what it said

Every completion SHALL keep its prompt, its completion text and the reason
generation stopped, beside the `model_calls` row recording what it cost. A token
count cannot be turned back into what a model was asked or what it answered, so
text not kept when the call is made is lost for good (ADR 0007).

Keeping it MUST be performed by the provider base class, for the reason
recording a call is: an implementation cannot forget what it never writes.

The text SHALL be written to disk under a configured root before the row that
names it is recorded, and the row SHALL hold paths relative to that root and
sizes read back from what landed.

A write that fails SHALL be recorded as a failure, and the caller SHALL still
receive its completion. The call happened and its answer is usable; losing the
night to the disk under the payload directory would turn a telemetry fault into
a product fault, and losing the text silently would be the gap this exists to
close.

The text is the most sensitive data the system holds. It SHALL be written only on
the machine that made the call, and nothing that serves a request, syncs, or
exports MAY read it.

#### Scenario: A completion keeps its text
- **WHEN** a reasoner returns a completion
- **THEN** its prompt, its completion and its finish reason are on disk under the payload root, and a row references them by relative path with sizes matching the files

#### Scenario: A truncated completion keeps why it stopped
- **WHEN** generation stops at a token limit
- **THEN** the kept completion records that reason, so the text read back later is not mistaken for a finished answer

#### Scenario: The disk refuses the write
- **WHEN** the payload root cannot be written
- **THEN** the caller receives its completion, no payload row names a missing file, and a failure scoped to payloads is recorded

#### Scenario: Tests never write where real payloads live
- **WHEN** the test suite runs
- **THEN** every payload is written under that test's own temporary directory
