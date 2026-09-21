# Own the machine: backup, restore, and a check that says it is well

## Scale classification

**L2 — Feature.** One new package, one CLI, two documents, no schema change and
no change to any request path. It carries a `design.md` because one technical
choice is load-bearing and gets got wrong by default — how to copy a SQLite
database that is in WAL mode while something may be writing to it — and because
the recovery procedure's shape is an argument, not a setting.

## Why

`docs/SPEC_ROADMAP.md` gives this capability one line and the line is the
problem: *"The machine: reboot story, backups, a recovery procedure someone has
actually executed. Nobody owns it."* Four prompts mention deploying to that
machine. None owns what happens when it fails.

What is on it, from `OPERATIONS.md`'s verification of 2 Sep:

- `~/second-shift-data/second-shift.db` — four real captured entries and the
  week-1 eval baseline, which is the left-hand side of the submission's
  centerpiece. **There is no second copy.**
- `~/second-shift-data/artifacts/` — what the night writes.
- The brain, a git repository mirrored to a NAS with no remote.

`grep -rn backup` over the repository returns three unrelated docstrings.
**Nothing backs up the database, and nothing ever has.** `docs/WEEK_ONE.md` is
explicit that a memory history which starts late cannot be recovered; one that is
lost is worse, and the eval baseline pins a rubric hash that cannot be
reconstructed from anything in git.

## What changes

**`secondshift/ops/`, with `python -m secondshift.ops` as its entry point** —
matching `night/`, `evals/` and `brain/`, which are the packages that already
own a verb.

| Command | What it does |
|---|---|
| `backup` | Writes a consistent copy of the database and the artifacts tree, with a manifest, to a destination the operator names. |
| `restore` | Rebuilds from a backup onto a path, refusing to overwrite by default, and verifying what it wrote against the manifest. |
| `verify` | Checks a backup without restoring it: the manifest matches the bytes, and the database inside opens and has the schema it claims. |
| `doctor` | The post-deploy check. Exits non-zero when the machine is not well. |

**The database is copied through SQLite's own online backup API**, never `cp`.
A WAL-mode database is three files and the `.db` alone can be stale or torn;
this is argued in `design.md` and demonstrated by a test that copies a database
mid-transaction both ways and shows the naive copy losing committed rows.

**The manifest is the verification.** Per-table row counts, `schema_version`,
the artifact file count and total bytes, a digest per member, and the
instant — so a restore can be checked against what was taken rather than
against a hope.

**`doctor` is what the prompt says has never been run.** It resolves the
configuration, opens the database, confirms WAL and that migrations are current,
checks the reasoner endpoint on the port `config/models.toml` allocates and that
it serves the name the probe expects, reports how old the newest backup is, and
warns when it is running as a user whose home is not where the data lives.

**`deploy/spark/deploy.sh` takes a backup before it destroys anything.** It
already `rm -rf`s the remote tree; the data lives outside that tree, so this is
insurance rather than a fix, and insurance that costs a second is worth its line.

**`docs/operations/RECOVERY.md`** — the procedure, stating for every step
whether it has been executed and where.

## The open decisions

**Recorded as markers, not answered.** Both are the user's: one is where their
data is allowed to live, the other needs knowledge of what is mid-flight on a
machine this session cannot reach.

**Where the backup is kept, and on what schedule.** The constitution decides the
*constraint* and not the target: the brain never leaves, and an export path that
includes `model_call_payloads` is named as a Privacy Airlock violation. A backup
of this database contains raw unredacted entry text and every prompt and
completion the system has ever sent, so it is the most sensitive artifact the
project produces and it may not leave the premises. Which on-premises target
holds it, and how often, is a decision about their network.
`[NEEDS CLARIFICATION]` in `design.md`, with a recommendation.

**Whether the reasoner container becomes a supervised unit now.** The unit exists
and is the safer shape; the running container is not it. Switching costs a
restart and about three minutes of model load. `OPERATIONS.md` says to weigh
that against what is mid-flight, and nothing in this repository knows what is.
`[NEEDS CLARIFICATION]` in `design.md`, with a recommendation.

## What this change cannot do, and says so

**This session has no route to the always-on machine.** `tailscaled` is not
running here and there is no tailnet interface; the container sits behind a
proxy shim with no path to that network. So:

- The **mechanism** is built here and executed here, against a real WAL-mode
  database with a writer active, and timed.
- The **procedure on that machine** — a reboot, a restore of the real data, and
  `python -m secondshift.config show` run there for the first time — is not
  done, is not claimed, and is listed in `docs/SPEC_ROADMAP.md` as what a
  machine session owes.

A recovery document that has never been followed is a hypothesis. This one has
been followed against a database that is not the one that matters, which is more
than nothing and less than the claim, and it says which.

## Impact

**Affected specs:** `operations` (new).

**Affected code:** `apps/api/secondshift/ops/` (new), `deploy/spark/deploy.sh`,
`docs/operations/RECOVERY.md` (new). No route, no migration, no schema change.

## Constitution Compliance

| Principle | Bearing | How this change stands |
|---|---|---|
| 1. Brain plaintext under git | **Constrains** | A backup must not create a second thing that believes it is the original. The brain is a git repository already mirrored to a NAS, and this change does not touch it, copy it, or add a remote to it — `backup` names the brain in its manifest as deliberately excluded, with the reason, so an operator reading the manifest learns the brain is somebody else's job rather than assuming it is covered. |
| 2. The Privacy Airlock | **Constrains, and is the sharpest risk here** | A backup is a complete copy of every captured idea and every recorded prompt and completion. The constitution names an export path including `model_call_payloads` as a violation, so the destination is an airlock decision: the spec forbids a destination outside the machine's trust boundary and the tool states what the archive contains every time it writes one. The marker above asks which on-premises target, never whether it may leave. |
| 3. No empty mornings | Not engaged | Nothing here runs during a night. |
| 4. Text-first, voice layered | Not engaged | No surface change. |
| 5. One codebase, two deployments | **Constrains** | `doctor` reads the same resolved configuration both deployments read and branches on none of it. A judge container that runs it gets an answer about itself; there is no personal-instance path. |
| 6. Scope boundary | Respected | Operations is not a product surface. No route, no screen, nothing a user of the product sees. |
| 7. Telemetry from line one | **Considered, and deliberately not applied** | `backup` and `doctor` make no agent invocation and no model call, so there is no invocation or `model_calls` row for them to write. Writing an `events` row for a backup would put operational noise in a night's timeline, which the scrubber renders — and the timeline is a record of what the night did, not of what the operator did. The manifest is the backup's own record, and it is more durable than a row in the database being backed up. |

No violation. Nothing blocking.

## Risk

**A backup nobody has restored.** The whole point of the capability, so the
restore is executed in the test suite against a real database and once by hand
with a measured time, and `verify` exists so that checking a backup does not
require trusting one.

**A `doctor` that passes on a broken machine.** Every check is proved able to
fail by breaking the thing it checks. A check that cannot go red is worse than
no check, because it reads as evidence.

**Scope creep into a monitoring service.** `OPERATIONS.md` excludes one by name:
the telemetry database is the monitoring. `doctor` is a command somebody runs,
not a daemon, and it exits with a status rather than emitting anything.
