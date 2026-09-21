# 0014 — A backup never leaves the premises

**Status:** accepted · **Date:** 2026-09-21

## Context

The always-on machine holds the only copy of the database: four real captured
entries, the week-1 eval baseline and the rubric hash it pins, and every night's
telemetry. Nothing backed it up and nothing ever had.

Adding a backup makes the sensitive question concrete rather than theoretical. A
backup of this database is not a subset of it — it is a complete second copy of
every captured idea and, in `model_call_payloads`, every prompt and completion
the system has ever sent. Until now that content existed in exactly one place
and its reachability was a property of one machine. A backup makes it a file
that somebody has to decide where to put.

Principle 2 already names the shape of the answer. "An export path that includes
`model_call_payloads`" is listed in the constitution as what a violation looks
like, and `0001_initial.sql` says of that table that it "must never be synced,
uploaded, or included in a judge deployment." ADR 0012 puts the machine behind a
single tailnet origin. Principle 1 puts the brain on a NAS mirror with no
remote.

What was missing was the statement that a backup inherits all of it.

## Decision

**A backup of this database may not leave the boundary that holds the brain.**

No cloud object store, no off-site service, no third-party backup product, at
any price and behind any encryption. The question a destination has to answer is
not "is it encrypted" but "is it inside the boundary" — and a destination
outside it is refused whether or not the bytes at rest are readable.

The tooling takes a destination as a required argument and has no default
anywhere, so choosing one is always a deliberate act. It states what the archive
contains every time it writes one.

## Consequences

- **The recovery story is bounded by the premises.** A fire that takes the
  machine and the NAS takes the data. That is accepted: the alternative is an
  off-site copy of every captured idea, and this product's central claim is that
  those do not leave. A privacy guarantee that has an exception for backups is a
  privacy guarantee with an exception.

- **"Encrypted at rest" is not an argument that reopens this.** It is a good
  property and it does not change the boundary. Encryption moves the risk from
  the storage provider to the key, and the key would live on the same machine
  the backup exists to survive the loss of.

- **A redacted export is a different artifact and not a backup.** If off-site
  durability is ever wanted, the thing that goes off-site is something that has
  been through the airlock, and it is not restorable — it is evidence, not a
  copy. Anything restorable contains what a restore needs, which is everything.

- **The judge deployment is unaffected.** Its database is synthetic by
  construction and `scripts/check-judge-package.py` already refuses one carrying
  `model_call_payloads` rows. That check and this decision are the same rule at
  two boundaries.

- **Cost: the backup destination is one more thing to configure, per deploy.**
  `deploy.sh` requires `SPARK_BACKUPS` alongside the host and the account. A
  default would be one less variable and the way a copy of every captured idea
  ends up somewhere nobody chose.

- **This constrains capabilities that do not exist yet.** Anything that syncs,
  archives, or offers to "keep a copy for you" inherits it. A future change that
  wants an off-premises copy needs a superseding ADR, not a configuration flag.
