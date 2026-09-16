## ADDED Requirements

### Requirement: An answer is input only to the idea it was asked about

A queued answer SHALL be handed only to runs of the entry its decision was
raised against, and SHALL be marked consumed only by a run that closed with an
outcome other than `failed`.

#### Scenario: Another idea's answer is not handed to this run
- **WHEN** one entry has an answer queued for tonight and a different entry runs
- **THEN** that answer appears in none of the second entry's stage context, and remains queued for its own entry

#### Scenario: A failed run leaves the answer queued
- **WHEN** a run that took a queued answer closes as `failed`
- **THEN** the decision is not marked consumed and is offered to the entry's next run

### Requirement: An answer queued for tonight gives the idea another night

Answering a question with the `queued-for-tonight` status SHALL return its
entry from `answered` to `queued`, so the answer has a night to reach.

#### Scenario: The loop closes in the order it happens
- **WHEN** a night runs an entry, raises a question, and that question is answered with `queued-for-tonight`
- **THEN** the entry is eligible for dispatch, and its next run receives the answer and is recorded as having consumed it

#### Scenario: Other outcomes leave the idea where it is
- **WHEN** a question is answered as decided, deferred or obsolete
- **THEN** the entry's status is unchanged

### Requirement: The interviewer is shown only its own night

The interviewer SHALL be given the facts of the run it follows and no other.

#### Scenario: Another run's facts are not in the interview
- **WHEN** two entries run and the interviewer runs for the second
- **THEN** nothing from the first run appears in what the interviewer is given

### Requirement: A briefing says when the interviewer could not run

Where the interviewer failed for a run in the briefing, the briefing SHALL
carry that failure's message.

#### Scenario: A broken interviewer is reported
- **WHEN** the interviewer raises for a run in the briefing
- **THEN** the briefing's interviewer error carries the failure message

### Requirement: Answering is safe to retry

Resubmitting the answer and status a decision already holds SHALL succeed and
return the stored decision. A different answer to an answered decision SHALL be
refused as a conflict.

#### Scenario: A retried answer succeeds
- **WHEN** the same answer is submitted twice for one decision
- **THEN** the second submission succeeds and returns what the first recorded

#### Scenario: A conflicting answer is a conflict
- **WHEN** a different answer is submitted for an answered decision
- **THEN** it is refused with a conflict rather than not-found
