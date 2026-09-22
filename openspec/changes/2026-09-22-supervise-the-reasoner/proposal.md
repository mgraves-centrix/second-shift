# Supervise the reasoner, without killing a night to do it

## Scale classification

**L1 — Small task.** One command, one check, one procedure document. The switch
itself is three commands on the always-on machine and this session has no route
to it, so what ships here is the part that can be made correct in advance: the
precondition, and the trap that would otherwise be found at 15-second intervals.

## Why

`2026-09-21-add-operations` recorded a marker: whether the reasoner container
becomes its supervised unit now, or after the next machine session.
`OPERATIONS.md` says to weigh it against what is mid-flight, and nothing in this
repository knows what is.

**Answered 22 Sep: now.**

The reasons the marker gave still hold. The container publishes `0.0.0.0:8200`
while the unit binds `127.0.0.1:8200:8000`, so today's arrangement is reachable
by anything that reaches the machine — the one part of this reconciliation that
is a privacy question rather than an uptime one. And every day it runs
unsupervised is a day a reboot ends local inference silently, which is the
failure the unit's own header comment says it was written after.

## The trap, found while preparing the switch

**`ExecStartPre` removes the wrong container.**

| | |
|---|---|
| The unit removes | `second-shift-reasoner` |
| The container actually running | `nemotron-lightning` |

The `ExecStartPre` carries a leading `-`, so removing a container that is not
there succeeds silently. Then `docker run -p 127.0.0.1:8200:8000` fails, because
`nemotron-lightning` still holds host port 8200. `Restart=always` with
`RestartSec=15` turns that into a unit failing every fifteen seconds **while the
reasoner appears healthy**, because the old container is still serving on the
port the probe checks. `ops doctor` would report the reasoner fine. So would the
capability probe. The only thing that would be wrong is the thing the switch was
for.

That is a documentation problem rather than a code one — the unit is correct for
a machine where the old container is gone — so the procedure removes it by its
real name first, and says why.

## The precondition, which is code

`docker rm -f` on the reasoner during a night kills the night.

A night in flight is knowable exactly: `night/__main__.py` holds an advisory
`flock` on `<db>.night.lock` for the duration of a run, released by the kernel
however the process exits. That lock is a better signal than an open `runs` row,
which is also what a night killed last week leaves behind — the distinction
`recover_interrupted` exists for.

**`python -m secondshift.ops night-status`** exposes it: exit 0 when the machine
is idle, exit 3 when a night holds the lock, reusing the night's own
`EXIT_ALREADY_RUNNING` so the two commands cannot drift into different codes for
the same state.

It composes, which is the point:

```bash
python -m secondshift.ops night-status && systemctl --user enable --now second-shift-reasoner
```

`doctor` reports the same state as a line, because "is a night running right
now" is worth knowing before a deploy, a restart or a reboot, not only before
this one switch.

## What changes

- `ops night-status`, and a `night in flight` line in `doctor`.
- `docs/operations/SUPERVISING_THE_REASONER.md` — the switch, in order, with
  the container-name step and what each step is protecting.
- The marker in the archived change, answered in place.

## Impact

**Affected specs:** `operations` (one added requirement).

**Affected code:** `apps/api/secondshift/ops/doctor.py`, `__main__.py`. No unit
file changes — the units were already right; what was wrong was the assumption
that the machine matched them.

## Constitution Compliance

| Principle | Bearing | How this change stands |
|---|---|---|
| 1. Brain plaintext under git | Not engaged | — |
| 2. The Privacy Airlock | **Constrains, and is the reason for the timing** | The running container publishes on every interface; the unit binds loopback. Principle 2 makes the machine's reachability an airlock decision rather than an operations convenience, and this narrows it. Nothing here widens anything. |
| 3. No empty mornings | **Constrains** | The whole precondition exists because restarting the reasoner mid-night costs that night its morning. A check that a person can forget is not a guard, so it exits non-zero and composes with `&&`. |
| 4. Text-first, voice layered | Not engaged | — |
| 5. One codebase, two deployments | **Constrains** | `night-status` reads a lock file beside the configured database and knows nothing about which deployment it is on. The judge container has no night and reports idle, correctly. |
| 6. Scope boundary | Respected | No product surface. |
| 7. Telemetry from line one | **Considered, deliberately not applied** | Reads a lock. No model call, no invocation, and an `events` row for "somebody asked whether a night was running" would put the operator in the night's own timeline. |

No violation.

## Risk

**The procedure has not been run.** It cannot be from here. Every step says what
it is protecting so that a step that fails is legible rather than mysterious,
and `docs/SPEC_ROADMAP.md` carries it as owed rather than done.

**`night-status` reports idle on a machine whose night died holding the lock.**
Correct, and worth stating: the kernel releases the lock when the process exits
however it exits, so a dead night does not hold it. What that leaves is an open
run, which is `recover_interrupted`'s job at the start of the next night, not
this command's.
