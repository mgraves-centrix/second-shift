# morning-interview Specification

## Purpose
What the night did, what it could not decide, and the answers that change
tonight. The briefing is assembled from rows rather than narrated by a model, so
a failing interviewer costs the questions and not the morning; the delta it
covers runs from the last decision a person *acted* on, because rendering a
briefing is not the same as reading it; and an answer is always given against a
specific question the system asked, which is what keeps this an interview rather
than a chat interface.

## Requirements

### Requirement: The briefing covers every run since the last answered decision

The briefing SHALL include every run started after the most recently answered
decision. Rendering a briefing SHALL NOT advance that boundary; only acting on a
question SHALL.

#### Scenario: A night nobody acted on still appears the next morning
- **WHEN** a briefing is assembled, rendered without any question being answered, and assembled again the next morning
- **THEN** the second briefing still contains that night's run

#### Scenario: Two nights with no interview between them both appear
- **WHEN** two nights run with no decision answered between them
- **THEN** the briefing covers both runs rather than only the most recent

#### Scenario: Answering advances the boundary
- **WHEN** a question is answered and a later run completes
- **THEN** the next briefing covers the later run and not the runs before the answer

#### Scenario: Deferring counts as acting
- **WHEN** a question is deferred rather than decided
- **THEN** the boundary advances, because deferring is a choice the person made

### Requirement: A partial night is presented, never an error

The briefing SHALL report the stages that reached `complete` together with those
that failed or were skipped and the reason each gave. It SHALL NOT substitute an
error for partial results.

#### Scenario: A half-failed night shows what succeeded
- **WHEN** a run completed some stages and failed others
- **THEN** the briefing lists the completed stages and their artifacts alongside the failures

#### Scenario: A skipped stage is distinguishable from a failed one
- **WHEN** a stage was skipped with a reason and another failed
- **THEN** the briefing reports them differently rather than collapsing both into "did not run"

#### Scenario: A briefing is available when the interviewer cannot run
- **WHEN** the interviewer model call fails
- **THEN** the briefing's facts are still assembled and returned, with no questions

### Requirement: A question carries the reason the agent could not proceed

Every decision raised SHALL record a rationale, and SHALL name the invocation
that raised it.

#### Scenario: A raised question records its rationale
- **WHEN** the interviewer raises a question
- **THEN** the stored decision has a non-empty rationale

#### Scenario: A raised question is attributable to an interviewer invocation
- **WHEN** the interviewer raises a question
- **THEN** the decision names that agent invocation, so a prompt change is visible in the record

### Requirement: An answer is given against a specific question

An answer SHALL be accepted only against an existing decision. No path SHALL
accept free-form instructions and route them.

#### Scenario: Answering an unknown question is refused
- **WHEN** an answer is submitted against a decision that does not exist
- **THEN** it is refused rather than recorded

#### Scenario: Answering records the modality
- **WHEN** a question is answered by typing
- **THEN** the decision records the answer with the `text` modality

#### Scenario: An answer queued for tonight is readable as tonight's input
- **WHEN** a question is answered with the `queued-for-tonight` status
- **THEN** it appears among the decisions awaiting a run, and once consumed it names the run that consumed it

#### Scenario: Deferring and marking obsolete are outcomes, not deletions
- **WHEN** a question is deferred or marked obsolete
- **THEN** the decision is retained with that status rather than removed

### Requirement: Widening a policy requires an attributable decision

A run SHALL widen `local-only` to `cloud-assisted` only where an answered
decision authorizes it, and the recorded policy source SHALL say so.

A question raised against a `local-only` entry SHALL be marked in the briefing
as one whose answer can authorize sending the idea off the machine. A question
raised against an entry that is already `cloud-assisted` SHALL NOT be marked,
because there is nothing left to widen.

#### Scenario: An authorized widening records its source
- **WHEN** a run resolves with a decision authorizing the widening
- **THEN** the run's effective policy is `cloud-assisted` and its policy source is `decision-upgrade`

#### Scenario: Widening without a decision is refused
- **WHEN** a `local-only` entry is resolved with no authorizing decision
- **THEN** the policy stays `local-only`

#### Scenario: The person is told before the idea leaves
- **WHEN** a question is raised against a `local-only` entry
- **THEN** the briefing marks that question as one whose answer can send the idea off the machine

#### Scenario: A question about an idea that already left is not marked
- **WHEN** a question is raised against a `cloud-assisted` entry
- **THEN** the briefing does not mark it, because widening is not what its answer would do

### Requirement: Every turn completes without speech

Each interview turn SHALL be completable by typing, as the primary path rather
than as a fallback.

#### Scenario: The interview completes with no microphone
- **WHEN** an interview is conducted with no speech input available
- **THEN** every question can be answered and the interview reaches its end

#### Scenario: No turn requires a modality that is unavailable
- **WHEN** the answer path is inspected
- **THEN** `text` is accepted without any speech capability being present

### Requirement: The interview is conducted one question at a time

The morning surface SHALL present a single open question at a time, with the
number of questions remaining visible. Reaching a later question SHALL require
disposing of the current one, and every outcome — including deferring — SHALL
advance the interview.

#### Scenario: The agenda has a visible length
- **WHEN** the morning surface renders more than one open question
- **THEN** the person can see how many there are and which one they are on

#### Scenario: Deferring advances the interview
- **WHEN** a question is deferred
- **THEN** the interview moves to the next question rather than leaving the deferred one in place

#### Scenario: The interview ends
- **WHEN** every question has been disposed of
- **THEN** the surface says the interview is finished rather than rendering an empty question

#### Scenario: The questions keep the order the interviewer asked in
- **WHEN** an interviewer turn raises several questions
- **THEN** the briefing returns them in the order they were asked, including when they were raised within the same millisecond

### Requirement: The morning surface accepts no instruction without a question

Every answer control on the morning surface SHALL be rendered within a specific
question and SHALL submit against that question's decision id. The surface SHALL
NOT provide a path that submits text without one.

#### Scenario: There is no unattached submit path
- **WHEN** the morning surface's answer path is inspected
- **THEN** every submission carries a decision id, and no request is made to a route that accepts text alone

#### Scenario: An answer records its modality
- **WHEN** a question is answered by typing
- **THEN** the submission records the `text` modality explicitly

### Requirement: A partial night is rendered, never an error

The morning surface SHALL render the stages that completed alongside those that
failed or were skipped, and SHALL distinguish a stage whose reason was not
recorded from one that had none.

#### Scenario: A half-failed night renders what succeeded
- **WHEN** a run completed some stages and failed others
- **THEN** the surface shows the completed stages and their artifacts alongside the failures

#### Scenario: An unrecorded reason is not shown as no reason
- **WHEN** a stage was skipped and no reason was persisted
- **THEN** the surface says the reason was not recorded rather than leaving it blank

#### Scenario: A failed interviewer does not remove the facts
- **WHEN** the briefing reports that the interviewer could not run
- **THEN** the night's record is still rendered, with a line saying why there are no questions

#### Scenario: Nothing to report is not an error
- **WHEN** there are no runs since the last answered decision and no open questions
- **THEN** the surface says so plainly rather than rendering an error or an empty page

#### Scenario: An empty morning claims nothing about a night that did not run
- **WHEN** there are no open questions and no runs to report
- **THEN** the surface makes no statement about what the night did

### Requirement: A failed answer says the answer was not recorded

Where submitting an answer fails, the surface SHALL say the answer was not
recorded and SHALL retain what was typed.

#### Scenario: A submission that fails is reported as unrecorded
- **WHEN** an answer submission does not succeed
- **THEN** the surface reports that the answer was not recorded, and does not advance the interview

#### Scenario: The typed answer survives a failed submission
- **WHEN** an answer submission fails
- **THEN** the text that was typed is still present

### Requirement: The interview requires no microphone

Every turn SHALL be completable by typing, and the morning surface SHALL NOT
depend on any speech capability being present.

#### Scenario: No speech API is referenced
- **WHEN** the morning surface is inspected
- **THEN** it references no microphone or speech recognition API

#### Scenario: The interview completes by typing alone
- **WHEN** an interview is conducted with no speech input available
- **THEN** every question can be answered and the interview reaches its end
