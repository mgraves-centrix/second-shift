# Operations prompt

Paste as the first message of a fresh session. **Requires access to the
always-on machine.**

**Independent of every capability. Owns the deploy path and the machine.**

---

Own the deployment and recovery story. Read `openspec/constitution.md`,
`CLAUDE.md`, and `docs/SPEC_ROADMAP.md` first; they are the rules, not
background.

## Why this one

Four prompts mention the machine. **None owns it.** Deploying, surviving a
reboot, and recovering from a disk failure are everyone's assumption and nobody's
task, which is the same shape as the two defects already on the record: a gate
recorded as met that was never met, and an evidence document specified in a
directory tree that was never written.

The stakes are specific. That machine holds **the only copy** of the database —
four real captured entries and the week-1 eval baseline — and the brain, which
is the left-hand side of the submission's centerpiece. `docs/WEEK_ONE.md` is
explicit that a memory history which starts late is not recoverable at all. One
that is *lost* is worse.

## What already exists — do not invent any of it

Verified on the machine 2 Sep:

- `second-shift-api.service` (user) — **running**, uvicorn on `127.0.0.1:8080`.
- `second-shift-brain-sync.service` and `.timer` (user) — **running**, firing.
- `loginctl` linger is **enabled**, so user services start without a login. An
  earlier note saying this was pending is stale.
- `nemotron-lightning` — a Docker container, up for days, publishing `0.0.0.0:8200`
  and listening on 8200 internally. **It has no systemd unit and did not come
  from one.**
- `deploy/spark/second-shift-reasoner.service` — written 2 Sep, **never
  started**. It binds loopback and maps 8200 to 8000, which differs from the
  running container in both respects. The unit is the safer shape; reconcile them.
- `deploy/spark/deploy.sh` — builds the web export, tars, and does `rm -rf` on the
  remote tree before extracting. It now refuses to replace a target rubric that
  differs from the one being shipped, with `SECOND_SHIFT_RUBRIC_OVERWRITE` as the
  documented override.
- The brain is a git repository on that machine, mirrored to a NAS, with no
  remote.
- The API reaches the phone through `tailscale serve`, which is what gives it the
  secure context `getUserMedia` and the service worker require (Spike A).

## The open decision

**What the recovery procedure is, and whether it has ever been executed.**

If that disk fails today, what is lost and how long does it take to get back?
Nobody knows, because nobody has tried. The brain is mirrored to a NAS; the
database is not obviously mirrored anywhere; the deployed tree is reproducible
from git, and the *data* is not.

**Do not decide this by preference and do not write a procedure you have not
run.** Decide it by executing a restore onto a scratch path on that same machine
and timing it. A recovery document that has never been followed is a hypothesis,
and this is the one place where being wrong costs something that cannot be
rebuilt.

The second open thing: **whether the reasoner container becomes a systemd unit
now.** It has been up for days without one, so the cost of switching is a
restart and about three minutes of model load — and the benefit is surviving a
reboot. Weigh it against what is mid-flight, and do it deliberately rather than
as a side effect.

## What good looks like

- **The machine reboots and everything comes back** without anyone logging in:
  API, brain sync, reasoner. Tested by actually rebooting it.
- A restore procedure that **you have executed**, with a measured time to
  recovery and an explicit list of what is lost in the worst case.
- The database is backed up somewhere that is not that disk, on a schedule, and
  a backup has been restored at least once.
- `deploy.sh` is safe to run without thinking: it refuses when it would destroy
  something, and what it destroys is reproducible from git.
- The reasoner's unit and the running container agree, and the port matches
  `config/models.toml` — which the capability probe checks and which has already
  been wrong once.
- Nothing on that machine is reachable from the public internet.

## Scope — what NOT to build

- **No orchestration platform.** No Kubernetes, no Compose stack, no Ansible.
  Systemd units and a shell script, matching what is there.
- **No monitoring service.** The telemetry database is the monitoring.
- **No CI that deploys.** Nothing in the repository should be able to touch that
  machine automatically.
- **No public exposure.** The tailnet is the network boundary and it stays that
  way unless an ADR says otherwise.
- **No secrets in tracked files.** This capability writes deployment
  configuration, which is exactly where hostnames and usernames leak.

## Constitution hooks

- **Principle 1.** The brain lives on the always-on machine and a laptop copy is
  a clone, never the original. Backups must not create a second thing that
  believes it is the original.
- **Principle 2.** The machine holds every captured idea. Anything that widens
  its reachability is an airlock decision, not an operations convenience.
- **Principle 5.** The same code runs here and on the judge instance. Deployment
  differences are configuration, never a branch.

## The loop

```bash
git status --short
scripts/check-no-environment.sh && scripts/check-american-english.sh
apps/api/.venv/bin/python -m pytest apps/api/tests -q          # 302 pass today
```

Then, against the machine:

```bash
python -m secondshift.evals status     # the data that must survive
systemctl --user list-units --type=service --all | grep second-shift
systemctl --user list-timers --all | grep second-shift
```

**Never run `uv run` there** — it re-resolves the environment to x86_64 and
destroys it. `python -m venv` plus `pip` with pinned constraints.

## Verification — reboot it

- **Reboot the machine and watch everything come back.** That is the test. Not
  `systemctl status`, not "linger is enabled" — an actual reboot, and every
  service serving afterward.
- **Execute the restore** onto a scratch path and diff the result against the
  live database. Report the time it took.
- `deploy.sh` refuses to overwrite a differing rubric — **prove it can fail** by
  pointing it at a modified one and watching it stop, then at a matching one and
  watching it proceed. The stub-based tests already do this; confirm against the
  real host.
- The capability probe reports the reasoner available afterward, by name, on the
  port `config/models.toml` allocates.
- Capture works from the phone after everything above. **It is live and taking
  real ideas**; if it breaks and you cannot fix it in ten minutes, revert to the
  last known-good commit, redeploy, verify, and stop.

## Quality bar

The code is the submission. Judges read this repository.

**Never ship:** a recovery procedure you have not run; a backup that has never
been restored; a hostname, address, username or home path in a tracked file; a
unit that disagrees with the running process; a deploy that destroys something
without saying so; a `TODO`.

**Always:** use placeholders and environment variables for anything
machine-specific; make destructive steps refuse by default; prefer the boring
construction; let failures be loud. American English. Both check scripts pass
before every commit.

## Hard stops

Stop, record the question with your recommendation, and move on:

- A `[NEEDS CLARIFICATION]` marker. Do not answer your own.
- A constitution violation. Blocking, not advisory.
- **Widening the machine's network exposure.** Public endpoints, port forwards,
  or anything reachable outside the tailnet is an ADR-level decision.
- **Deleting data.** Including "cleaning up" old databases, WAL files or
  containers you did not create.
- Credentials, payment, account settings.
- Rewriting published history or force-pushing.

## Report

1. The restore you executed, the time it took, and **what would still be lost.**
2. The reboot, and what did not come back the first time — if everything did,
   say so, and say whether you believe it.
3. Whether the reasoner is now supervised, and the reconciliation between the
   unit and the container.
4. What shipped, with test counts.
5. Anything blocked, with your recommendation.
6. What you would do next, and why that rather than the alternative.
