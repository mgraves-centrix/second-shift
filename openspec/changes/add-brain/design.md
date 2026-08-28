## Context

The brain repository exists at a sibling path, seeded and committed. Capture
writes entries to SQLite. Nothing joins them.

Two constraints shape everything here. The brain is plaintext under git, so
every operation is file I/O and a subprocess — no library, no abstraction over
either. And capture must never fail, so nothing in this change may run inside a
request.

## Goals / Non-Goals

**Goals:**
- Captured entries reach the journal, in order, durably.
- Topic files are readable by the orchestrator.
- A run and an eval score are attributable to an exact brain state.
- A brain falling behind is visible.

**Non-Goals:**
- Writing topic files back. That is the distiller, and it does not exist.
- Retrieval or embedding over the brain. Separate capability, and per ADR 0002 it
  is brute-force over SQLite blobs when it arrives.
- Any night behaviour.

## Decisions

### Journaled-ness is derived from the journal

The journal records each entry's identifier. What has been journaled is
determined by reading the journal files, not by a column.

A stored flag would need a migration, and worse, it could disagree with the
files — a row saying "journaled" while the file says otherwise is a bug nothing
detects until the week-8 diff is short. The journal is the only thing that knows
what is in the journal.

Cost: sync reads the current and recent journal files each time. At five to ten
entries a day this is a few kilobytes. If the journal ever grows enough for that
to matter, the fix is an index derived from the files, not a flag beside them.

*This is the same argument that made quarantine derived rather than stored, and
it is becoming a pattern worth naming: where a fact is already recorded
somewhere authoritative, deriving beats storing.*

### Git is a subprocess, not a library

Four commands: `rev-parse HEAD`, `status --porcelain`, `add`, `commit`. A git
library would add a dependency and an object model to do what those already do,
on a repository whose whole point is being ordinary enough to open by hand.

Every invocation is scoped with `-C <brain path>`. None runs from a request.

### Sync is idempotent and interruptible

Sync appends missing entries and commits. Running it twice appends nothing the
second time, because the journal already names those entries. An interrupted
sync leaves either an uncommitted journal or a committed one, and the next run
resolves both — appending nothing and committing what it finds.

That property is what allows sync to be triggered by a timer without any locking
against itself beyond a simple guard.

### The journal is written for a human first

One file per local date, entries in capture order, each with its identifier,
instant, policy and text. The identifier is what makes derivation possible, but
the format is chosen for someone reading a day's ideas in a text editor — because
a memory nobody can read by hand is the opaque store the constitution forbids,
whatever format it is in.

### `brain_sha` is read at run start

A run pins the brain's HEAD when it begins, not when it ends, because the brain
state that shaped the run is the one it started from. Eval runs do the same, and
day 5 scoring against the day-3 baseline depends on it: the score must be
attributed to the brain that produced the output, not to HEAD at scoring time.

## Risks / Trade-offs

**The brain has no schema and no constraints.** Every other store in this system
refuses malformed data. The brain accepts anything, and a bug that writes broken
markdown surfaces as an unreadable diff in week 8 rather than an error in week 3.
Mitigation is narrow: sync writes through one function, that function is tested
against the real format, and a round-trip test reads back what it wrote.

**Timer frequency is a latency-versus-noise trade.** Frequent sync keeps the
brain current and produces more commits; infrequent sync batches them and leaves
a window where a crash loses nothing but the brain looks stale. Entries are
durable in SQLite either way, so this is about how quickly the brain reflects
reality, not about safety.

**Hand-editing and automation share a working tree.** The user is expected to
edit `profile.md` — the seeded version explicitly asks to be corrected. An
automated commit that sweeps up a half-finished edit is worse than one that
refuses. This is the second open question, and it is a question about respecting
someone's unfinished work rather than a technical one.
