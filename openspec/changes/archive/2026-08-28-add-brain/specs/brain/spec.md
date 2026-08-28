## Purpose

The plaintext memory as a system boundary: captured entries reaching a
git-versioned journal, topic files readable by the orchestrator, and a brain
state pinned to every run that depends on it.

## ADDED Requirements

### Requirement: Captured entries reach the journal

Every captured entry SHALL be appended to a dated journal file in the brain, in
capture order, recording at least its identifier, capture instant, policy and
content.

The journal is organized by the entry's own local date, derived from the
timezone captured with it — not the server's date at sync time.

#### Scenario: An entry is journaled
- **WHEN** sync runs with a captured entry not yet in the journal
- **THEN** the entry appears in the journal file for its own local date, and the brain is committed

#### Scenario: Entries appear in capture order
- **WHEN** several entries are journaled together
- **THEN** they appear ordered by capture instant, not by the order they reached the server

#### Scenario: A drained offline entry files under its own date
- **WHEN** an entry captured late on one day is received the next morning
- **THEN** it is journaled under the date it was captured, not the date it arrived

### Requirement: Journaling is derived and idempotent

What has been journaled SHALL be determined by reading the journal, not from a
stored flag. Running sync repeatedly MUST NOT duplicate an entry.

#### Scenario: Sync run twice
- **WHEN** sync runs, then runs again with no new entries
- **THEN** the second run appends nothing and creates no commit

#### Scenario: Interrupted sync resolves itself
- **WHEN** a previous sync wrote the journal but did not commit
- **THEN** the next sync commits the existing content without duplicating any entry

#### Scenario: No stored journaled flag exists
- **WHEN** the schema is inspected
- **THEN** no column records whether an entry has been journaled

### Requirement: Sync commits its own work only

Sync SHALL stage and commit only the journal, never the whole working tree. A
change elsewhere in the brain — a topic file edited by hand and not yet
committed — MUST be left untouched and uncommitted.

One commit SHALL cover everything a single sync run journaled, naming what it
covered.

#### Scenario: A hand-edited topic file is left alone
- **WHEN** sync runs while the profile has uncommitted edits
- **THEN** the journal is committed, the profile edit remains uncommitted, and the commit contains only journal changes

#### Scenario: Journaling is not blocked by an unfinished edit
- **WHEN** an uncommitted edit has been sitting in the brain overnight
- **THEN** sync still journals and commits the night's entries

#### Scenario: One commit per sync run
- **WHEN** sync journals several entries in one run
- **THEN** exactly one commit is created, and its message names how many entries and which dates it covered

### Requirement: Sync never runs inside a request

Journaling and committing SHALL be a separate operation, invoked on a schedule or
on demand. A capture request MUST NOT perform git work.

#### Scenario: Capture does not commit
- **WHEN** an entry is captured
- **THEN** the request completes without invoking git, and the entry is journaled by a later sync

#### Scenario: An unavailable brain does not break capture
- **WHEN** the brain repository is missing or unreadable
- **THEN** capture continues to succeed and entries accumulate for a later sync

### Requirement: A brain that falls behind is visible

Sync SHALL fail loudly when the brain cannot be written, recording a typed
failure. It MUST NOT skip silently.

The number of entries captured but not yet journaled SHALL be retrievable.

#### Scenario: The brain is missing
- **WHEN** sync runs against a path that is not a git repository
- **THEN** it fails with a typed failure naming the path, and no entry is marked as handled

#### Scenario: Backlog is observable
- **WHEN** entries exist that are not in the journal
- **THEN** the count of unjournaled entries is retrievable without reading the journal by hand

### Requirement: Topic files are readable by the orchestrator

The system SHALL read the brain's topic files — the profile, the style guide,
and the skills directory — and make their content available to later stages.

Reading MUST tolerate a file being absent: a brain with no skills yet is a new
brain, not a broken one.

#### Scenario: Topic files are read
- **WHEN** the orchestrator loads the brain
- **THEN** the profile and style guide content are available, and the skills directory is enumerated

#### Scenario: A new brain with no skills
- **WHEN** the skills directory is empty
- **THEN** loading succeeds and reports no skills, rather than failing

### Requirement: Brain state is pinned to runs

A run and an eval run SHALL record the brain's commit at the moment it started,
so any output is attributable to the exact memory state that produced it.

#### Scenario: A run pins the brain
- **WHEN** a run begins
- **THEN** it records the brain's current commit

#### Scenario: Scoring against a recorded state
- **WHEN** an eval baseline recorded on one day is scored on a later day
- **THEN** the score is attributed to the brain commit recorded at baseline, not to the brain's current state

#### Scenario: An unavailable brain does not invent a commit
- **WHEN** the brain cannot be read at run start
- **THEN** no commit is recorded, rather than a placeholder that would later look like a real state
