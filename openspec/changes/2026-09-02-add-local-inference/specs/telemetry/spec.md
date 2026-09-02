## ADDED Requirements

### Requirement: A failure escaping a provider backend is recorded

Where a provider's backend raises, the failure SHALL be recorded and classified
before the exception propagates.

Recording MUST NOT swallow the exception, and MUST NOT convert a failure into a
successful call.

#### Scenario: A backend raises
- **WHEN** a provider's backend raises during a call
- **THEN** a classified failure is recorded and the exception continues to the caller

#### Scenario: The failed call is not recorded as a call
- **WHEN** a completion fails
- **THEN** no model call row is written for it, because a row with no tokens and no answer would appear in the cost curve as a call that happened
