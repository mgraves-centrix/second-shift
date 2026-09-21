# Recovery

What to do when the always-on machine is gone, and how much of this anybody has
actually done.

**Every step carries a status.** A procedure nobody has followed is a
hypothesis, and one where some steps are exercised forty times a day by the test
suite while others have never been run is two documents pretending to be one.
Read the status column before you read the step.

| Status | Means |
|---|---|
| **exercised** | Runs in `apps/api/tests/test_operations.py` on every gate. |
| **rehearsed** | Executed by hand, against a generated night rather than the real data. Timings below are from that. |
| **never run** | Nobody has done this. Read it carefully and expect it to be wrong somewhere. |

---

## What is lost in the worst case

The machine holds the only copy of three things. They are not equally
recoverable, and the differences matter more than the list.

| | Recoverable from | If the disk fails today |
|---|---|---|
| The database | Nothing but a backup | **Everything since the newest backup.** Captured entries, every night's telemetry, the eval baseline and the rubric hash it pins. |
| Artifacts | Nothing but a backup | Everything since the newest backup. Regenerable in principle by re-running the nights; in practice the nights consumed a brain that has since moved on. |
| The brain | Its NAS mirror | Whatever the mirror has not caught. Not this procedure's job — see below. |
| The deployed tree | git | Nothing. `deploy.sh` rebuilds it. |

**The eval baseline is the one that cannot be reconstructed.** It pins a rubric
hash and a brain hash to a measurement taken in week one, and
`docs/WEEK_ONE.md` is explicit that a memory history which starts late is not
recoverable at all. A baseline that is lost cannot be re-taken later and made to
mean the same thing, because the brain it measured no longer exists.

**The brain is deliberately not backed up by this tooling.** It is a git
repository already mirrored to a NAS. Principle 1 says memory lives in its own
repository and a copy is a clone, never the original; a second backup path would
create a third thing, and two systems disagreeing about which is authoritative
is a worse failure than the one they were built to prevent. Every manifest names
this exclusion with the reason, so an operator reading one learns the brain is
somebody else's job rather than inferring from silence that it was included.

---

## Taking a backup

**Status: exercised.** Also runs on every deploy, before anything is replaced.

```bash
python -m secondshift.ops backup --to <directory>
```

There is no default destination and there will not be one. A copy of every
captured idea and every recorded model payload should not be able to land
somewhere nobody chose.

**It may not leave the boundary that holds the brain.** Principle 2 names an
export path that includes `model_call_payloads` as a violation, and
`0001_initial.sql` says of that table that it must never be synced or uploaded.
No cloud destination is available for this archive at any price.

What it writes, under a timestamped directory:

```
2026-09-21T21-10-39Z/
  second-shift.db     the database, through SQLite's online backup API
  artifacts/          what the night wrote
  manifest.json       per-table row counts, schema version, a digest per member
```

The database is **never** copied as a file. It runs in write-ahead logging mode,
so committed transactions — including `CREATE TABLE` — live in the `-wal` file
until a checkpoint moves them. Copying `second-shift.db` alone after five
hundred committed inserts produces a database in which the table does not exist,
and that failure restores cleanly: it looks like a successful recovery of a
machine that had nothing on it. `TestTheMechanismIsTheRightMechanism` keeps the
demonstration.

## Checking a backup without restoring it

**Status: exercised.**

```bash
python -m secondshift.ops verify <backup>
```

Every member against its recorded digest, the database against `integrity_check`
and against the manifest's own counts. Exits non-zero and names what disagrees.
A restore runs this first and refuses a backup that fails it — restoring damage
over a working database turns one problem into two, and the damage was knowable
beforehand.

## Restoring

**Status: rehearsed.** Executed against a generated night, not against the
machine's data. See the measurements below, and the caveat under them.

```bash
python -m secondshift.ops restore <backup>              # refuses an occupied path
python -m secondshift.ops restore <backup> --overwrite  # says that is what you meant
```

It verifies, writes the database and the artifacts, removes any `-wal` and
`-shm` left beside the target — a write-ahead log belonging to a different
database is read as that database's committed tail — and then compares what
landed against the manifest. A count that disagrees fails loudly rather than
reporting success because nothing raised.

### Measured, 21 Sep

Against a generated night: 1,896 rows across 17 tables, a 768 KiB database, 8
artifact files, with a second connection holding an open write transaction
throughout the backup.

| | |
|---|---|
| Backup | **0.116 s** |
| Backup on disk | 844 KiB |
| Restore | **0.120 s** |
| Restored database vs. original | **byte-identical** dumps, 439,949 bytes |
| The writer's uncommitted row | correctly absent |

**What this does not measure.** That database is a generated one on a container
filesystem. The real machine's database is smaller today and will not stay that
way, and neither number says anything about the throughput of that disk. Treat
these as evidence that the mechanism is correct, not as a recovery time
objective.

## Checking the machine

**Status: exercised. Never run on the always-on machine.**

```bash
python -m secondshift.ops doctor --backups <directory>
```

Six checks, all of them reported rather than stopping at the first failure:
configuration resolves; the database opens in WAL with a current schema; the
data path is not the root account's default; the local reasoner answers on the
configured port serving the expected name; and the newest backup is not stale.
Exits non-zero if any fail. `deploy.sh` runs it at the end of every deploy.

`python -m secondshift.config show` has still never been run on that machine —
`doctor` subsumes its first check, and running both after the next deploy is
worth the ten seconds.

---

## From nothing: rebuilding the machine

**Status: never run.** Every step below is written from what the deploy script
and the units do, not from having done it. Expect it to be wrong somewhere.

1. Install the OS, Docker, and Tailscale. Join the tailnet.
2. Create the service account. `sudo loginctl enable-linger <account>` — user
   services do not start without a login otherwise, and this is what makes the
   API survive a reboot.
3. Clone this repository on a development machine and deploy:
   ```bash
   SPARK_HOST=<host> SPARK_USER=<account> SPARK_BACKUPS=<dir> deploy/spark/deploy.sh
   ```
   The deploy ships to a staging path, takes a backup, and only then replaces
   the live tree. On a machine with no data yet the backup is of an empty
   database, which is correct and costs nothing.
4. Restore the newest good backup:
   ```bash
   python -m secondshift.ops verify <backup>
   python -m secondshift.ops restore <backup>
   ```
5. Install the units. They need sudo, so the deploy script prints them rather
   than running them:
   ```bash
   sudo cp deploy/spark/second-shift-api.service /etc/systemd/system/
   sudo systemctl daemon-reload && sudo systemctl enable --now second-shift-api
   ```
   The reasoner and embedder have both a system and a user variant. The user
   variants need no sudo and no substitution.
6. Restore the brain from its NAS mirror. `git clone` from the mirror, and check
   that the result's log is the one you expect before anything writes to it.
7. Expose the API:
   ```bash
   tailscale serve --bg --https=443 http://127.0.0.1:8080
   ```
8. `python -m secondshift.ops doctor --backups <dir>` and read every line.
9. Capture an idea from the phone. That is the acceptance test, and nothing
   above substitutes for it.

## What a machine session still owes

Listed here and in `docs/SPEC_ROADMAP.md`, because an obligation recorded only
in the document that assumes it is a dropped one.

- **A reboot.** Not `systemctl status`, not "linger is enabled" — an actual
  reboot, with the API, the brain sync and the reasoner serving afterward.
- **A restore of the real data** onto a scratch path, diffed against the live
  database, and timed.
- **`doctor` on that machine**, whose `data ownership` check exists because a
  service running as the wrong account has corrupted the write-ahead log there
  before.
- **The reasoner container reconciled with its unit.** The container was started
  by hand and publishes on every interface; the unit binds loopback. A reasoner
  reachable from anything that reaches the machine is a privacy question, not an
  uptime one.
- **A backup schedule**, once its destination is decided.
