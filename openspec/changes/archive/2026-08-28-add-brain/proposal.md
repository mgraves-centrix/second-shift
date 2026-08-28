## Why

Three ideas are queued and none of them is in the brain. Capture writes to
SQLite; the brain is a folder of markdown under git, and nothing currently
connects them.

That gap is the whole submission. The centerpiece is running a fixed prompt in
week 1 and week 8 and diffing the brain between them, and a brain that no
entries reach has nothing to diff. Every night of dogfooding without this is a
night whose ideas exist only in a database — which is precisely the "opaque
store" the first constitution principle forbids as the source of truth.

The brain repository exists, is seeded, and is backed up. What is missing is the
orchestrator reading from it and writing to it.

## What Changes

**Journal.** Every captured entry appends to a dated markdown file in the brain,
in capture order, and the brain is committed. The journal is the raw record: what
was captured, when, under what policy.

**Reading.** The orchestrator reads the topic files — `profile.md`,
`style-guide.md`, `skills/*.md` — so later stages can use them. This change reads
them; nothing writes them back yet, because that is the distiller's job and it
does not exist.

**Pinning.** `runs.brain_sha` and `eval_runs.brain_sha` are populated from the
brain's actual HEAD, so a run or an eval score is attributable to the exact
memory state that produced it. Without this the week-1 baseline cannot be scored
against the week-1 brain on day 5, which is the whole point of splitting it.

**Sync is out of the request path.** Capture does not commit. A git operation in
an HTTP handler makes the one interaction that must never fail depend on a
subprocess, a lock file and a disk — and the design doc for capture already
reserved this seam rather than taking it.

Not in this change: the distiller writing topic files, retrieval or embedding
over the brain, and the interview reading it. Those are separate capabilities.

## Capabilities

### New Capabilities
- `brain`: the plaintext memory as a system boundary — journaling captured
  entries into it, reading its topic files, and pinning its state to runs.

### Modified Capabilities
None.

## Constitution Compliance

| Principle | Status | Note |
|---|---|---|
| 1. Brain plaintext under git | **Implements** | This is the principle. Markdown in a sibling repository, diffable, never vendored into this repo and never the database. |
| 2. Privacy Airlock | Compliant | The brain never leaves the machine. Journaling is local file I/O and a local commit; no provider is involved and no policy check applies because nothing is transmitted. |
| 3. No empty mornings | Compliant | A failed journal sync must not lose an entry: entries stay in SQLite and are journaled on the next attempt. |
| 5. One codebase, two deployments | Compliant | The brain path is configuration. The judge deployment points at its own seeded brain; no branch in the code. |
| 7. Telemetry from line one | **Implements** | Journal writes and commits are recorded as events against the entry, so a brain that falls behind is visible rather than silently stale. |

No violations.

## Decisions taken without a marker

- **Journaled-ness is derived, not stored.** Which entries are already in the
  journal is determined by reading the journal, which is the only thing that
  actually knows. No column, no migration, and no flag that can drift from the
  files it describes — the same argument that made quarantine derived.
- **Sync is a separate operation**, invoked on a timer and on demand, never from
  a request handler.
- **A missing or unreadable brain is loud.** Sync fails visibly rather than
  skipping; a brain silently not being written is indistinguishable from a brain
  with nothing to write until the week-8 diff is empty.
- **The journal records the entry's own content.** The brain is local by
  construction and never transmitted, so there is nothing to redact at this
  boundary. Redaction applies at egress, which is a different seam.
- **Synthetic entries journal to the deployment's own brain.** The path is
  configuration; the judge instance has its own, so no filtering is needed.

## Impact

**New:** `secondshift/brain/` — repository access, journal writing, topic file
reading. A sync entry point invoked by a timer.

**Changed:** run creation populates `brain_sha`.

**Dependencies:** none. Git is invoked as a subprocess; a library would add a
dependency to do what four commands already do.

**Risk:** the brain is the one store with no schema and no constraints. A bug
that writes malformed markdown is not caught by anything, and the failure mode
is a diff nobody can read in week 8 rather than an error in week 3.

## Resolved Decisions

Settled via `/openspec:clarify` on 2026-08-28.

**One commit per sync batch.** Each run commits everything it journaled, with a
message naming the count and the dates covered.

At a short timer interval that is a handful of commits a day — ordered, readable,
and few enough that a hand-edit to `profile.md` stays visible in `git log`
rather than buried. Per-entry commits would produce hundreds over eight weeks and
recreate inside the brain the exact burying that ADR 0001 separated the
repositories to avoid.

Within-night ordering is not lost: it lives inside each journal file, which is
where someone reading a day's ideas would look for it.

**Sync commits only the journal paths.** A hand-edited `profile.md` is staged by
nobody and committed by nobody; sync stages `journal/` and commits that alone.

Your unfinished thought stays yours, and journaling never stalls waiting for you
to finish it. Refusing to sync would mean an edit left overnight costs a night of
ideas reaching the brain — the exact failure this capability exists to prevent.

The cost is accepted: the working tree stays dirty, so `brain_sha` describes HEAD
rather than what is on disk. That is the right attribution anyway — a run is
shaped by committed memory, not by an edit in progress.

This also protects the one signal the eight-week diff depends on: which changes
were *learned* and which were *told*. Sweeping a human edit into an automated
commit would blur exactly that.
