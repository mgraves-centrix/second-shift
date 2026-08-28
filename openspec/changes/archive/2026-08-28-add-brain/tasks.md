## 1. Brain repository access

- [x] 1.1 Configure the brain path — environment variable, falling back to a sibling directory, with no real path baked into the repository.
- [x] 1.2 Wrap the four git operations needed — head commit, porcelain status, add, commit — each scoped with `-C` and none invoked from a request.
- [x] 1.3 Read topic files: profile, style guide, and the skills directory, tolerating any of them being absent.
- [x] 1.4 Test: reading a brain with no skills succeeds and reports none.
- [x] 1.5 Test: an absent or non-git path is reported as unavailable rather than raising.

## 2. The journal

Depends on group 1.

- [x] 2.1 Write the journal format: one file per local date, entries in capture order, each carrying identifier, instant, policy and content, formatted for someone reading a day in a text editor.
- [x] 2.2 Derive journaled identifiers by reading the journal files, with no stored flag.
- [x] 2.3 Report the count of captured entries not yet journaled.
- [x] 2.4 Test: an entry is written and read back with its identifier, instant and content intact.
- [x] 2.5 Test: entries are ordered by capture instant, not by arrival order.
- [x] 2.6 Test: an entry captured late one day and received the next files under its capture date, using its own timezone.

## 3. Sync

Depends on group 2.

- [x] 3.1 Implement sync: append every unjournaled entry, then commit, recording an event against each entry journaled.
- [x] 3.2 Make sync idempotent — a second run with no new entries appends nothing and creates no commit.
- [x] 3.3 Resolve an interrupted sync: commit an existing uncommitted journal without duplicating entries.
- [x] 3.4 Fail loudly with a typed failure when the brain is missing or unwritable, marking nothing as handled.
- [x] 3.5 Add a command-line entry point so sync can be invoked by a timer and by hand.
- [x] 3.6 Test: sync twice creates one commit and one set of entries.
- [x] 3.7 Test: an uncommitted journal from a prior run is committed without duplication.
- [x] 3.8 Test: a missing brain produces a typed failure and leaves entries unjournaled.
- [x] 3.9 Test: capture succeeds and performs no git work while the brain is unavailable.

## 4. Pinning

Depends on group 1.

- [x] 4.1 Populate the brain commit on run creation, read at run start.
- [x] 4.2 Record no commit rather than a placeholder when the brain cannot be read.
- [x] 4.3 Test: a run records the brain's current commit.
- [x] 4.4 Test: an eval baseline recorded earlier is scored against its recorded commit, not the current one.
- [x] 4.5 Test: an unreadable brain leaves the commit unset rather than inventing one.

## 5. Deployment and gates

- [x] 5.1 Add a systemd timer that runs sync, alongside the existing user service.
- [x] 5.2 Gate: the three already-captured entries appear in the journal, under their own dates, and the brain is committed.
- [x] 5.3 Gate: full suite passes on the Spark, transferred with AppleDouble sidecars suppressed.
- [x] 5.4 Gate: `openspec validate --strict` for the change and every canonical spec.
- [x] 5.5 Gate: no environment details enter the repository — the check script passes.
- [x] 5.6 Update the roadmap and the week plan with what shipped and what the eval baseline now depends on.
