# Take the backup every night, onto a disk that is not this one

## Scale classification

**L1 — Small task.** One systemd unit, one line on an existing unit, one guard
and one check. Under a day, one component. No `design.md`: the decision it
implements was already argued in `2026-09-21-add-operations`'s design and is now
answered, and the one new idea here is small enough to carry its own comment.

## Why

`2026-09-21-add-operations` shipped the mechanism and recorded the schedule as a
clarification marker, because where a copy of every captured idea lives is a
decision about somebody's network rather than about code.

**Answered 22 Sep: the NAS, nightly after the night run.**

That is what the marker recommended, and the reasons it gave still hold — the
NAS already holds the brain's mirror, so it adds no trust boundary; and
coupling the schedule to the night means a machine that stops running nights
stops producing backups, which is a signal rather than a silent success.

## What changes

**`deploy/spark/second-shift-backup.user.service`** — a `oneshot` that runs
`python -m secondshift.ops backup`. Ordered `After=second-shift-night.service`,
and pulled in by the night's own `Wants=`, so it runs when the night finishes
rather than at a clock time somebody guessed the night would be done by.

**It runs after a night that failed, too.** `Wants=` does not care how the
wanted unit exited, and that is deliberate: the night most worth having a copy
of is the one that went wrong.

**The destination comes from `%h/.config/second-shift/backup.env`**, which is
not in this repository and never will be. `EnvironmentFile=` without the leading
`-`, so a missing file fails the unit loudly rather than starting a backup with
nowhere to put it.

**A backup refuses to land on the disk it exists to survive.** This is the new
idea, and it is a failure this schedule creates: if the NAS is not mounted, the
mount point is an ordinary empty directory on the local disk, and a nightly
backup writes into it for weeks. Every backup succeeds, `doctor` reports them
fresh, and the copy is on the one device whose failure the whole capability is
about. So `ops backup` compares the destination's device against the database's
and refuses when they match, with `--same-device-ok` for a deliberate local
rehearsal — the same shape as `restore --overwrite`.

**`doctor` gains a check for it**, because a backup that started landing locally
three weeks ago is a state you want reported rather than discovered.

## Impact

**Affected specs:** `operations` (two added requirements).

**Affected code:** `apps/api/secondshift/ops/backup.py`, `doctor.py`,
`__main__.py`; `deploy/spark/second-shift-backup.user.service` (new) and one
line on `second-shift-night.user.service`.

## Constitution Compliance

| Principle | Bearing | How this change stands |
|---|---|---|
| 1. Brain plaintext under git | **Constrains** | The NAS already holds the brain's mirror. This writes the database's backup beside it and still does not touch the brain, which has its own path there; two systems disagreeing about which copy of the brain is authoritative is the failure Principle 1 exists to prevent. |
| 2. The Privacy Airlock | **Constrains** | ADR 0014: a backup may not leave the boundary that holds the brain. The NAS is inside it — it is on the tailnet and already trusted with the more sensitive of the two. Nothing here widens the machine's reachability, and the same-device guard makes the destination's identity checkable rather than assumed. |
| 3. No empty mornings | **Considered** | The backup is ordered after the night, so it cannot compete with the work that produces a morning. A backup that failed does not fail the night: they are separate units and the night has already finished by then. |
| 4. Text-first, voice layered | Not engaged | — |
| 5. One codebase, two deployments | **Constrains** | A unit is deployment configuration, not a branch. The judge container runs the same `ops` and simply has no timer installed. |
| 6. Scope boundary | Respected | No product surface. |
| 7. Telemetry from line one | **Considered, deliberately not applied** | Still no model call and no agent invocation. `journalctl --user -u second-shift-backup` is the record of a unit, and the manifest is the record of a backup; an `events` row would put operational noise in a night's timeline, which the scrubber renders. |

No violation.

## Risk

**The night stops, and so do backups.** Accepted deliberately — it is the signal
the marker's recommendation was chosen for. `doctor`'s staleness check is what
turns it into a visible one, and three days is three missed nights.

**The mount check is wrong for a machine with one disk.** True, and that machine
should not be relying on these backups. `--same-device-ok` exists for the
rehearsal, and the refusal names the flag.
