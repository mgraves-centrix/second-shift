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

#### Scenario: An authorized widening records its source
- **WHEN** a run resolves with a decision authorizing the widening
- **THEN** the run's effective policy is `cloud-assisted` and its policy source is `decision-upgrade`

#### Scenario: Widening without a decision is refused
- **WHEN** a `local-only` entry is resolved with no authorizing decision
- **THEN** the policy stays `local-only`

#### Scenario: The person is told before the idea leaves
- **WHEN** a question would widen a policy if answered
- **THEN** the briefing marks that question as one whose answer sends the idea off the machine

### Requirement: Every turn completes without speech

Each interview turn SHALL be completable by typing, as the primary path rather
than as a fallback.

#### Scenario: The interview completes with no microphone
- **WHEN** an interview is conducted with no speech input available
- **THEN** every question can be answered and the interview reaches its end

#### Scenario: No turn requires a modality that is unavailable
- **WHEN** the answer path is inspected
- **THEN** `text` is accepted without any speech capability being present
