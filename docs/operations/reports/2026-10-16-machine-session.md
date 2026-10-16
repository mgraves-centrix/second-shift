# 2026-10-16 — the machine session

Driven from the laptop over SSH to `<spark>`. Every command below executed on
that machine; nothing ran locally but the web build that the deploy ships.

**Seven of the nine steps produced evidence. Two did not, and neither was a
judgement call I made.** Step 7 needs an idea queued and there are none; step 8
needs a password I do not have. The eval run — step 6, the deadline-critical
one — was started, found a defect in the instrument, and was stopped on purpose.
That is the most important thing in this report and it is in its own section.

---

## What the prompt assumed, and what was actually there

`ENDGAME.md` opens with `cd ~/second-shift && git pull origin main`. There is no
clone on that machine and there never was. `~/second-shift` is the tree
`deploy/spark/deploy.sh` lands: a tarball of `apps/api`, `apps/web/out`,
`packages`, `config` and `deploy`, with no `.git`, no `docs/`, no `openspec/`
and no `scripts/`. `git pull` there fails, and so does `python3 scripts/gate.py`.

More consequential: **the deployed tree predated `operations` entirely.** It had
no `secondshift/ops` package at all, so the first thing the newly installed
backup unit did was exit 1 with `No module named secondshift.ops`. The index's
line that "the deployed code predates all of it" was true and understated — the
gap was not stale code, it was a missing capability.

So the session did two things the prompt did not ask for, both preconditions
rather than scope creep:

- Cloned the repository to `~/second-shift-src` and built a venv there
  (`python3 -m venv` plus pinned `constraints.txt`, never `uv`). This is the
  session clone the prompt assumed existed. It is deliberately **not**
  `~/second-shift`, because `deploy.sh` does `rm -rf` on that path and would
  destroy a clone placed there.
- Ran `deploy.sh` to bring production up to `308e18a`. The rubric guard did not
  fire: the target's rubric already hashed `b4decd6fe774`, the same one the
  week-1 baseline is pinned to. The script took its own pre-deploy backup first.

After the deploy the schema was still at 2 against migrations going to 3.
Migration 0003 applies on startup through `api/context.py`, so restarting the
capture API applied it. Three additive `ADD COLUMN ... DEFAULT 0` and one index.

---

## The nine steps

### 1. `ops doctor` — evidence

First run, before anything was fixed, failed 3 of 8: schema at 2 against
migrations to 3; no backup in the configured directory; and the backup location
on the same device as the database. After the deploy, the migration and the NAS
destination, **all 8 pass**.

The `data ownership` check reports `named explicitly` and the database is owned
by the account the user units run as, which is also the account this session
logged in as. The SSH caveat in the prompt — that running `doctor` as a
different account reports on the wrong thing — does not apply here, and that was
confirmed rather than assumed.

### 2. A backup onto the NAS — evidence, both halves

The same-device guard was tested as a **control** before the real backup, and it
refused with exit 2 and named the cause, including the "if this is a network
share, it is not mounted" case it exists for.

The real backup landed on the NAS: 219 rows across 17 tables, 39 artifact files,
164,820 bytes. `ops verify` reported 40 members intact. Both exclusions printed
their reasons — the brain, and the deployed tree.

The unit is installed and `backup.env` written. The night unit now carries
`Wants=second-shift-backup.service`; it did not before, so the nightly backup
would never have been pulled in. A run of the unit after the deploy succeeded:
220 rows, schema 3.

**Where the backups go is a finding, not a decision I was comfortable making.**
The NAS exports four shares — `scratch`, `docker`, `datasets`, `models` — and
none of them is a backup share. The copy of every captured idea is currently
under `scratch`, on a volume whose name says it is disposable. That wants a
dedicated share.

`systemd-analyze --user verify` could not run over SSH: it needs a session bus
and reports `Failed to lookup RuntimeDirectory path`. The units were verified by
starting them instead.

### 3. A restore of the real data — evidence

Restored the newest NAS backup onto a scratch path, then compared against the
live database.

| | |
|---|---|
| `verify` of the backup, read from the NAS | 0.186 s |
| Restore onto a local scratch path | 0.174 s |
| Restored dump vs. live dump | **byte-identical**, 72,497 bytes each |
| Artifacts | `diff -r` clean, 39 files |

`RECOVERY.md`'s restore section can move from **rehearsed** to **run against the
real data**. Its 21 Sep timings were against a generated night on a container
filesystem; these are that machine and that data.

### 4. The reasoner onto its unit — evidence

The trap `SUPERVISING_THE_REASONER.md` describes was real and present. The
running container was `nemotron-lightning` publishing `0.0.0.0:8200`; the unit
removes `second-shift-reasoner`, which did not exist. A naive switch would have
failed every fifteen seconds while every probe reported the reasoner healthy.

`night-status` exited 0, the `&&` held, and the old container was removed by its
real name. Afterwards:

- `is-enabled` → `enabled`
- listening on `127.0.0.1:8200`, **not** `0.0.0.0` — the port is no longer open
  to the tailnet, which is the airlock half of the change
- container is `second-shift-reasoner`, `127.0.0.1:8200->8000`
- `doctor` 8 of 8

**It took about 300 seconds to serve, not the "roughly three minutes" the
procedure states**, from a warm cache. Worth correcting before somebody reads a
five-minute start as a hung unit.

### 5. `ModelJudge` against a real checkpoint — evidence, and it is not clean

This was named the single highest-risk item in the endgame. It was run against a
throwaway copy of the real database, per Principle 7: the rows were kept, the
database was thrown away.

**17 of 18 samples scored. One was refused.** Overall mean 16.53 out of 25.

| prompt | mean | sd | n |
|---|---|---|---|
| agent-memory-systems | 14.67 | 2.08 | 3 |
| been-avoiding | 19.33 | 0.58 | 3 |
| every-metric-dashboard | 16.00 | 5.29 | 3 |
| file-naming | 18.00 | 1.00 | 3 |
| readme-in-my-voice | 15.67 | 1.53 | 3 |
| shorter-briefing | 15.00 | 2.83 | **2** |

The extraction rule held on every call that produced a judgement: 18
generations, 18 judge calls, no retries, nothing truncated, completions between
roughly 6,400 and 12,700 tokens. The refusal was recorded as
`eval:shorter-briefing:UnreadableJudgement` and **not** as a zero, which is the
behavior the class exists for.

In its own words: `judgement is not structured data: Expecting value: line 1
column 30 (char 29)`.

### 6. The week-1 and week-8 runs — **stopped deliberately. Read this one.**

The week-8 baseline was recorded first, against the current brain
(`e68cecf9`), under the same rubric `b4decd6fe774` as week 1, so the curve
would not refuse on rubric or on the same brain being on both sides. Scoring
was started on **week 8 first and deliberately**, because its baseline is
reproducible — the brain cannot move while no night is queued — and week 1's
is the one thing in this system that cannot be retaken.

That ordering is what saved the baseline. **Five samples in, two had already
failed.** Both with the same error, at the same character offset as the smoke
test's single failure:

```
eval:agent-memory-systems:UnreadableJudgement
judgement is not structured data: Expecting value: line 1 column 30 (char 29)
```

I stopped the run. It was already unrecoverable, and here is why that matters
more than the wasted GPU time:

**A run that loses one sample can never be completed.** `eval_results` carries
`UNIQUE(eval_run_id, eval_prompt_id, sample_index)` and `EvalRunner.score`
regenerates every sample from scratch rather than topping up. A second `score`
on the same run id collides on the first already-recorded sample. The curve
refuses an incomplete run. So one unreadable judgement out of eighteen burns the
run permanently, and the only clean recovery is a fresh baseline — **which is
possible for week 8 and impossible for week 1.**

Measured failure rates: **1 of 18 against the week-1 brain, 2 of 5 against the
week-8 brain.** If the week-8 figure is near the truth, the probability of a
clean 18-sample run is low, and the week-1 baseline — the irreplaceable half of
the submission's centerpiece — would more likely than not have been destroyed by
running it. I was not willing to spend it on those odds without asking.

Run `01M53FX6MV5D9ZWF4Z6117YVSE` is now burned: three results recorded, still
reading `awaiting-scoring` because the process was killed before the closing
`UPDATE`, and un-rescorable because of the UNIQUE constraint. A fresh week-8
baseline costs nothing and should be recorded when scoring is attempted again.
**Run `01M1FYFECEXC5ZJEWHNP7WZMXB`, the week-1 baseline, is untouched.**

#### What the failure actually is, as far as it was proven

Char 29 is exactly the value slot of the first dimension in the judge's own
instruction template:

```
{"scores": {"interrogation": ␣
 0        1          2      ^ char 29
```

The strong hypothesis is that the served checkpoint sometimes echoes the
template from `_ASK` back verbatim, `<1-5>` placeholders and all, and
`last_object` dutifully extracts a syntactically balanced object whose first
value is not JSON. The offset is identical across all three observed failures,
which is not what randomness looks like.

**It was not reproduced.** Six attempts — three with synthetic filler, three
through the real generate-then-judge path on the exact prompt that failed twice
— all parsed cleanly. So the mechanism is indicated by the offset and not
confirmed by observation, and this report says so rather than asserting it.

The reason it could not be confirmed is the next finding.

### 7. One real night — **not attempted**

`entries` holds 7 real rows: 6 `answered`, 1 `archived`. **Nothing is queued**,
so there is no work for a night to do. Task 2.1 of
`2026-09-17-the-night-revises-what-it-believes` says so itself: "Needs an idea
queued."

Fabricating an entry would have put a made-up idea in the real database marked
`is_synthetic = 0`. Not done. This needs an idea captured from the phone, which
is also `RECOVERY.md`'s acceptance test.

Six real nights have run (three `complete` on 18 Sep), so the index's "Runs — 0.
No night has ever executed" is long stale.

### 8. A reboot — **not attempted, and not possible from here**

`sudo -n` reports `a password is required`. A session over SSH cannot reboot
that machine. Uptime is 5 weeks 5 days.

This is the step that proves the reasoner unit actually survives a restart, and
it is now the only thing standing between the unit work in step 4 and the claim
it was done to support. It needs somebody at that machine.

### 9. The judge container — evidence. **Built for the first time.**

`docker build -f deploy/judge/Dockerfile` succeeded on that machine. The seed
wrote its night at build time (5 entries, 182 invocations, 362 model calls),
and `check-judge-package.py` passed against the result inside the build.

Stood up and read:

- `/health` → `{"status":"ok"}`
- first screen, `/night/` → 200
- `/capabilities` → `profile: cloud`, `local-only` unavailable with the reason
  `no local reasoner is bound on this profile`. Exactly the honest message the
  Dockerfile argued for.
- every row in the image is `is_synthetic = 1`: runs, entries, all 362 model
  calls. `eval_runs` is empty.

Two findings a stranger would hit:

- **The image is `arm64`.** It was built on that machine, which is aarch64. ADR
  0009 puts this on a no-GPU x86 Compute VM, where this image will not run. It
  needs a cross-build before it is deployed anywhere.
- **The demo night has no outcome.** `/runs` returns the seeded night with
  `outcome: null`, `furthest_stage: null`, `ended_at_ms: null`. A judge opening
  the demo sees a night that never finished, which is a poor first impression
  for a product whose claim is that a night records what happened.

---

## `model_call_payloads` has never held a row, and nothing can put one there

`Repository.insert_model_call_payload` exists, is complete, and **has no caller
anywhere in the repository — not in the orchestrator, not in a test.** The table
is empty in the live database after six nights and an eval run, and empty in the
restored copy.

This is the same shape of defect as `close_run has no caller`, found 2 Sep and
closed. It costs three things:

- **`RECOVERY.md` is wrong where it matters.** Every backup prints that the
  archive "holds unredacted captured text and every recorded model payload."
  There are none.
- **`eval_results.output_path` is NULL for all 17 scored samples.** The
  submission's centerpiece will have numbers and no retained outputs behind
  them. Nobody will be able to read what actually changed between week 1 and
  week 8.
- **It is why step 6's failure could not be diagnosed.** The failing judgement
  was not kept, so the only evidence is a character offset.

`reports/README.md` says `model_call_payloads` "exists so that content stays on
that machine." The protection around it is real and carefully argued. The table
it protects is dead.

---

## The judge's prompt is not pinned

`eval_runs` records `judge_model` and `judge_model_version`, and
`judge_version` is a constant in `config/models.toml`. **The text of `_ASK` is
not hashed into anything.** The generating agent's prompt is pinned properly —
runs record `architect.v1:6e0066df513b` — so this is an asymmetry rather than a
missing idea.

It matters right now because the plausible fix for step 6 is an edit to `_ASK`.
Two runs scored either side of such an edit would pass every one of the curve's
ten refusals while having been measured by different instruments.

---

## The credential question

**Recommendation: leave it where it is. Nothing needs to move.**

The question in `ENDGAME.md` is framed around a cloud session needing a key in
the place the work is being done. This session was not a cloud session. Driving
the machine over SSH means every command runs **on** the machine, where
`~/.config/second-shift/secrets.env` already holds `NEBIUS_API_KEY`,
`NEBIUS_EXECUTOR_KEY_PATH`, `NEBIUS_SA_ID` and `TAVILY_API_KEY`. The two unrun
Nebius rows are reachable from a session shaped like this one without copying
anything anywhere.

What each answer costs, since the prompt asks for that:

- **Leave it.** `nebius-executor` work is done over SSH or at the machine. Costs
  nothing but the constraint that the work happens there. The RS256 Cloud IAM
  private key never exists in a second place.
- **Copy it.** Buys the ability to work from a cloud session. Costs a private
  key in a second location, permanently, to remove a constraint this session
  demonstrated is not binding.

The premise that made this a hard question — that the machine was unreachable
from where the work happens — did not hold today.

---

## What changed in `docs/SUBMISSION.md`

**Nothing yet, and that is correct.** No row moved from **not run** to a number:

- the week-8 eval score — still not run, deliberately, see step 6
- a real night proposing a belief — still not run, no idea queued
- a build fanned out to real Nebius Jobs — not attempted this session
- a cloud night's cost beside a local one — not attempted this session

The judge container row can move from "never built" to built, stood up and read,
with the arm64 caveat attached.

---

## The gate has never run there, and still has not

`scripts/gate.py` now exists on that machine in the session clone. It will not
pass yet:

- **No Chrome** — the browser gate cannot run
- **No `openspec` CLI** — the specs gate cannot run

Both are installable. Neither was installed, because installing a browser on the
always-on machine to satisfy a gate is a decision about that machine rather than
a step in this session.

---

## What I would do with the remaining days

Week 8 closes **Wed 21 Oct**. The deadline is **Fri 30 Oct**. Derive both rather
than trusting these.

1. **Retain payloads.** Wire `insert_model_call_payload` into the recorder. It
   is the smallest change here and everything else depends on it: without it the
   next judge failure is as undiagnosable as this one, and the submission's
   centerpiece ships without the outputs behind its numbers.
2. **Fix the judge, with the fix pinned.** Hash `_ASK` into `judge_version` so
   the instrument cannot change silently, then address the template echo — most
   likely by not showing a copyable `<1-5>` template in the ask. This is a
   change to how the submission's central number is produced, which is why this
   session stopped instead of making it.
3. **Then score both runs in one sitting**, week 8 on a fresh baseline, week 1
   last. Take a backup immediately before the week-1 scoring: a restore is the
   only retry that does not violate append-only, and it was proven today at
   0.174 s.
4. **The reboot**, from the machine. It is the only evidence that step 4 did
   what it was for.
5. **Queue an idea** and let a night run. That closes
   `2026-09-17-the-night-revises-what-it-believes` at 7/7.

Nebius and ASR come after all of it, and only if days remain. The alternative
ordering — score first, fix later — is the one that spends the week-1 baseline
on a coin flip, and the baseline is the single artifact in this project that
cannot be remade.

---

## State left on the machine

| | |
|---|---|
| `~/second-shift` | production, redeployed at `308e18a`, API serving, schema 3 |
| `~/second-shift-src` | the session clone, with its own venv. New today. |
| `~/second-shift-restore-test` | the throwaway restore and the smoke-test rows. Safe to delete. |
| `~/judge-probe*.py`, `~/judge-probe*-completions.txt` | reproduction attempts. The completion files hold model output and must stay on that machine. |
| `~/smoke-score.sh`, `~/score-run.sh`, `~/*.log` | the detached runners |
| `~/.config/second-shift/backup.env` | new; holds the NAS path |
| `~/second-shift-data/second-shift-night.service.pre-backup-unit` | the night unit as it was before the `Wants=` line |
| NAS | 4 backups under a `second-shift-backups` directory on the `scratch` share |
| docker | image `second-shift-judge` kept; the test container was removed |
