# Design — operations

## Context

The machine holds the only copy of four real captured entries, the week-1 eval
baseline, and every artifact a night has written. Nothing backs any of it up and
nothing ever has. This settles how a copy is taken, how it is proved good, what
the recovery procedure is, and — honestly — which parts of that procedure have
actually been run.

## Decision 1 — how a database in WAL mode is copied

This is the decision most likely to be got wrong by writing the obvious thing,
so it is settled by measurement rather than by reasoning about it.

The database runs `PRAGMA journal_mode = WAL` (`db/connection.py:35`), which
means it is three files: `second-shift.db`, `-wal` and `-shm`. Committed
transactions live in the `-wal` file until a checkpoint moves them, and a
checkpoint is not guaranteed to have happened at any particular moment.

### What was measured

A WAL database, a table created, five hundred rows inserted and committed, no
checkpoint forced. Then two ways of taking a copy:

| Method | What the copy contains |
|---|---|
| `cp second-shift.db backup.db` | **`sqlite3.OperationalError: no such table: t`** |
| `sqlite3.Connection.backup()` | 500 rows, `PRAGMA integrity_check` → `ok` |

The naive copy does not lose *some* rows. It loses the schema, because
`CREATE TABLE` was in the WAL too. A restore from it would present an empty
database that opens cleanly, which is the worst available failure: it looks like
a successful recovery of a machine that had nothing on it.

The online backup was taken while a second connection held an open write
transaction with an uncommitted insert. It contains the 500 committed rows and
not the uncommitted one — the correct answer, and the reason the API exists.

### The alternatives

**`cp`, or a `tar` of the data directory.** Rejected by the measurement above.
Copying all three files together is *sometimes* right and cannot be made
reliably right, because the three are not captured atomically.

**`VACUUM INTO`.** Produces a correct, compacted copy and is a single statement.
It takes a read lock for its whole duration and rewrites every page, so it is
slower on a large database and it blocks a checkpoint while it runs. It also
cannot report progress. Worth reconsidering if the database ever gets large
enough for the copy to matter; today it does not.

**`sqlite3 .backup` via the command line.** The same API through a binary that
may not be installed, and it puts the mechanism outside the test suite.

**`Connection.backup()`, the online backup API.** Copies page by page, restarts
if a writer changes a page mid-copy, holds no long lock, and is in the standard
library. It is what the measurement above used.

**Decision: `Connection.backup()`.** It is the only option that was demonstrated
correct under a concurrent writer, and the demonstration is kept as a test so the
next person does not have to take this document's word for it.

## Decision 2 — what a backup contains, and what it deliberately does not

**In:** the database, through the online backup API. The artifacts tree, which
is ordinary files nothing holds open. A manifest.

**Out: the brain.** It is a git repository already mirrored to a NAS.
Principle 1 says memory lives in its own repository and a copy is a clone, never
the original; a second backup path would create a third thing, and the failure
mode of two backup systems disagreeing about which is authoritative is worse
than the one they were built to prevent. The manifest names the brain as
excluded, with the reason, so an operator reading a manifest learns the brain is
covered elsewhere rather than assuming it is covered here.

**Out: the deployed tree.** Reproducible from git. `deploy.sh` already destroys
and recreates it.

**The manifest is the verification.** Per-table row counts, `schema_version`,
the artifact count and total bytes, a digest per member, and the instant. Every
one of those is something a restore can be checked against. A manifest carrying
only a timestamp would let a restore be declared successful by the fact that it
did not crash.

## Decision 3 — where a backup may live

The constitution decides the constraint and does not need asking.

A backup of this database contains raw unredacted entry text and every prompt
and completion in `model_call_payloads`. Principle 2 names "an export path that
includes `model_call_payloads`" as what a violation looks like, and `0001_initial.sql`
says of that table that it "must never be synced, uploaded, or included in a
judge deployment." **So a backup may not leave the machine's trust boundary**,
and no cloud destination is available for it at any price.

What is genuinely open is which on-premises target, and how often.

> `[NEEDS CLARIFICATION: Which on-premises target holds the database backup, and
> on what schedule? Recommendation — the same NAS the brain already mirrors to,
> written nightly after the night run finishes rather than on a wall-clock
> timer, so a backup is never taken in the middle of the only job that writes
> heavily. That target is already trusted with the brain, which is the more
> sensitive of the two, so it adds no new trust boundary; and coupling the
> schedule to the night means a machine that stopped running nights stops
> producing backups, which is a signal rather than a silent success.]`

The tool takes a destination as a required argument and has no default, so this
marker blocks the *schedule*, not the mechanism: a backup can be taken by hand
today, to anywhere the operator names.

## Decision 4 — what `doctor` checks, and what it refuses to become

`OPERATIONS.md` excludes a monitoring service by name: the telemetry database is
the monitoring. So `doctor` is a command a person runs after a deploy, exits
non-zero when the machine is not well, and emits nothing anywhere.

Each check exists because something specific has already gone wrong or is
recorded as able to:

| Check | Why it is there |
|---|---|
| Configuration resolves | `python -m secondshift.config show` "has never been run on the always-on machine" and exits non-zero on a malformed file. |
| The database opens, is in WAL, and its schema is current | A deploy that skipped a migration leaves a night failing at 2am with nobody watching. |
| The data directory belongs to the user running the check | `OPERATIONS.md`: "a `/root/...` database path in that output means the unit is running as the wrong user, which has broken the WAL before." |
| The reasoner answers on the configured port, serving the expected name | The port has already been wrong once, and `config/models.toml` is what the probe believes. |
| The newest backup's age | A backup schedule that silently stopped is indistinguishable from one that never existed, until the day it matters. |

`doctor` reports every check rather than stopping at the first failure. An
operator who fixes one thing and re-runs, three times, is being made to work for
information the first run already had.

## Decision 5 — whether the reasoner container becomes a supervised unit now

`deploy/spark/second-shift-reasoner.service` and its user variant exist, are
tested against `config/models.toml`, and bind `127.0.0.1:8200:8000`. The
container actually running was started by hand, publishes `0.0.0.0:8200`, and
has no unit. It has been up for days, so a reboot ends local inference silently
— which is the exact failure the unit's own header comment says it was written
after.

The unit is the safer shape in both respects: loopback rather than every
interface, and supervised rather than not. Nothing about the decision is
technical. What it costs is a restart and about three minutes of model load from
a warm cache, and `OPERATIONS.md` says to weigh that against what is mid-flight
— which nothing in this repository knows.

> `[NEEDS CLARIFICATION: Switch the reasoner to the systemd unit now, or after
> the next machine session? Recommendation — now, and specifically before any
> work that depends on local inference. The container currently publishes on
> every interface, which is a wider exposure than the unit's loopback binding
> and is the one part of this that is a privacy question rather than an uptime
> one; and every day it runs unsupervised is a day a reboot loses it without
> saying so. Three minutes is cheap unless a night is in progress.]`

This change adds a `doctor` check that reports the reasoner's reachability and
served name either way, so whichever is chosen, the answer is visible rather
than remembered.

## Decision 6 — what this change is allowed to claim

`OPERATIONS.md`: *"Do not decide this by preference and do not write a procedure
you have not run."*

This session has no route to the always-on machine — `tailscaled` is not running
and there is no tailnet interface. So the procedure is executed here, against a
real WAL-mode SQLite database with a concurrent writer, and timed; and
`RECOVERY.md` states per step whether it has been run and where.

The alternative was to write the procedure and mark the whole document
unverified. Rejected: "unverified" would have covered both the parts that are
genuinely untested and the parts that were executed forty times by the test
suite, and flattening those two into one word is how a document stops being
read. A per-step status costs a column and keeps the distinction that matters.

What remains untested, precisely: that the restore works against *that*
database, with *that* much data, on *that* filesystem, and that the machine
comes back from a reboot. Those are listed in `docs/SPEC_ROADMAP.md` as what a
machine session owes, not buried here.
