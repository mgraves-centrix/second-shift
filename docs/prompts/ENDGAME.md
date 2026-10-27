# Endgame — the machine session, and the order of everything after it

**Deadline: Fri 30 Oct 2026, 10:00 PT.** Solo.

```bash
python3 -c "from datetime import date; print((date(2026,10,30) - date.today()).days, 'days left')"
python3 -c "from datetime import date; print((date(2026,10,15) - date.today()).days, 'days to week 8')"
```

Derive both. A day count typed into this file ages into a lie that reads as
current, which is what happened to `00_INDEX.md` on 2 Sep.

**This is the one file in `docs/prompts/` that is not one session.** It owns the
*order* of the remaining sessions and the full prompt for the first of them,
because the first one unblocks the rest and nothing else can start until it
runs. Each later session has its own prompt already; this file says when.

---

## The window closed, and it costs less than this file used to say

Weeks run Thursday to Wednesday from 27 Aug, so week 8 was **Thu 15 Oct to Wed
21 Oct** and it passed unscored. The 16 Oct session recorded a week-8 baseline,
started scoring it, hit the judge defect five samples in and **stopped on
purpose** rather than spend the week-1 baseline on those odds. That was the
right call and this file is the one that was wrong: it treated the window as
the hard constraint when the irreplaceable thing is the week-1 baseline.

**What the delay actually costs is one word in the headline.** A later run
recorded now is week 9, not week 8. Nothing else moves, because the comparison
does not depend on when the scoring happens:

`EvalRunner.score` reads `brain_at_baseline(eval_run_id)` — the brain at the
commit the run pinned, not the brain on disk. So **scoring the week-1 baseline
today still produces a week-1 number.** The generation happens now; the memory
it generates from is the memory of 2 Sep. That is the property that makes "both
runs in one sitting" legitimate at any date, and it is worth checking in the
code before trusting this paragraph.

Derive the current week rather than reading a number here:

```bash
python3 -c "from datetime import date; print('week', (date.today() - date(2026,8,27)).days // 7 + 1)"
```

## What is left, and the one thing it waits on

Four claims in `docs/SUBMISSION.md` read **not run**, and after 10 Oct they are
no longer one blocker:

| | Needs |
|---|---|
| The eval score, both halves | **The machine only.** ADR 0015 made the judge local, so no credential. This is the submission's centerpiece and nothing else on this list is close |
| A real night proposing a belief against the real brain | The machine only, and an idea queued. Closes `2026-09-17-the-night-revises-what-it-believes` at 7/7 |
| A reboot | The machine itself. The one item the 16 Oct session could not do over SSH |
| The judge container **read by a stranger** | It was built and stood up 16 Oct. The image is `arm64` and needs a cross-build before it goes anywhere else |
| A build stage fanned out to real parallel Nebius Jobs | A credential, and `nebius-executor` is 3/23 |
| A cloud night's cost beside a local one | The same credential, plus the local night's rows |

`docs/SPEC_ROADMAP.md`'s **Owed verification → Open** table is the authoritative
list and is longer than this one. Read it before starting. Do not re-derive it
here; it moves.

## The order

1. **The machine session — the second one.** Everything below. Run it first,
   and run the eval inside it: the generation and the scoring both need the
   local reasoner, so splitting them across sessions buys nothing. It runs on
   the machine or over SSH from the laptop; see *Where this session runs*.

   The first one ran 16 Oct and its report is
   `docs/operations/reports/2026-10-16-machine-session.md`. **Read it before
   anything below** — it is the only account of what that machine actually
   does, and six of this file's old steps closed inside it.
2. **`SUBMISSION.md`** (the prompt, not the document): rewrite the measured
   table from the rows the machine session produced, and strike the claims that
   stayed unrun. The document already names its own unrun rows; the job is
   replacing them with numbers, not softening them.
3. **`NEBIUS_EXECUTOR.md`**, if and only if the credential question below is
   answered. It is the only remaining work that is a *feature* rather than a
   verification, and at 3/23 it is the one thing that could still be cut whole.
4. **`ASR.md`** last, and only if days remain. Text capture has been live since
   28 Aug, so voice gates nothing and never did.

---

# Session 1 — the machine session

Read `openspec/constitution.md`, `CLAUDE.md`, `docs/SPEC_ROADMAP.md`'s *Owed
verification* section and `docs/operations/RECOVERY.md` first. They are the
rules, not background.

## Starting it — the mechanics

**You do not need Claude on the machine to get the most valuable result.**
Steps 0 to 2 below are shell commands, and what they produce is a number a
person can read. Decide between these on how much judgment you want delegated,
not on what the file assumes:

| | What it buys | What it costs |
|---|---|---|
| **A terminal, no Claude** | Steps 0–2 in about twenty minutes: the deploy, `doctor`, and the smoke test that says whether the judge fix holds against a real checkpoint. That number decides whether step 4 is safe | Everything after is yours to sequence, and step 6's reconnect is manual |
| **`claude` in the clone on the machine** | All of it, adapting to what each step returns — which matters most at step 4, where a refused judgement is a finding about the instrument rather than a failure | A session running commands on the always-on machine, so read the boundaries first |
| **`claude` on a laptop, over SSH** | Everything that is pure commands, which is most of it | Cannot do the reboot well, and the four traps below all apply |

```bash
cd ~/second-shift && git pull origin main    # the judge fix and payload
                                             # retention are both newer than
                                             # the deployed tree
claude
```

Then paste `docs/prompts/MACHINE_SESSION_OPENER.md`, which is that text and
nothing else so it can be copied whole. It points back here rather than
restating any of this — one authority, so the two cannot drift apart.

Then paste this file. The clone on the machine already has a working virtual
environment, because it has been running nights — a **fresh** clone needs the
bootstrap in `docs/development/GATES.md` first, and the gate refuses by name
rather than guessing when it is missing.

### Handing the result back

Push it; do not paste it. `docs/operations/reports/README.md` is the contract.

```bash
git checkout -b reports/$(date +%F)-machine-session
# write docs/operations/reports/$(date +%F)-machine-session.md
git config core.hooksPath .githooks    # per clone; without it no check runs
git add docs/operations/reports/ && git commit && git push -u origin HEAD
```

A push touching only that directory runs the two source checks rather than the
suites, so this needs git and bash and not a web toolchain. **If it is refused
it will be a hostname or a home path** — use `<spark>` or `~/...` rather than
`--no-verify`. The machine's short name is also this project's compute-profile
name, so nothing can catch it by spelling and the check catches it by position.

## Where this session runs, confirmed 12 Oct

**On the always-on machine, or from a session on the laptop that drives it over
SSH.** Both work; neither is a cloud session.

A cloud container has no route — tested, and the test is recorded under *Owed
verification*, including the trap that makes a naive probe report success. The
laptop has SSH to the machine, so a session there can run the steps below
remotely. What it cannot do is run them *locally*: the database, the brain
repository and the model all live on the machine, so every command below
executes there whatever drives it.

Four things about the SSH route specifically, each of which will bite:

- **Write `<spark>`, never the machine's name.** The repository is public.
  `scripts/check-no-environment.sh` now enforces this for ssh invocations —
  added 12 Oct, because the short MagicDNS name is also this project's
  compute-profile name, so no pattern can catch it by spelling and the check
  catches it by position instead.
- **`ops doctor` checks data ownership, and over SSH you are whoever you logged
  in as.** That check exists because a service running as the wrong account
  corrupted the write-ahead log on that machine. Running it as a different
  account than the services use reports on the wrong thing — confirm who owns
  the database and who the units run as before believing the result.
- **The reboot drops the connection.** Step 6 ends the session that issued it.
  Expect the disconnect, do not read it as a failure, and reconnect to verify
  what came back up rather than inferring it from a command that never
  returned.
- **A real night outlives an SSH session.** Do not run step 5 in the foreground
  of a connection that can close. Use the installed timer, or `systemd-run`, and
  then watch `ops night-status` — a night killed by a closing terminal leaves a
  run to quarantine and teaches nothing.

## What already exists — do not invent any of it

- **`python -m secondshift.evals score <id>`**, since 10 Oct. It generates
  through `agents.invoke` with the `architect` role and grades with
  `ModelJudge`, and it **refuses rather than substituting** at every point where
  it could substitute: no judge configured, no local reasoner bound, no pinned
  version, a deployment scoring the other kind of run. On a profile that
  resolves to `cloud` it exits 2 and says so, because the registry binds an
  echo there and an echo's numbers are indistinguishable from a model's once
  recorded.
- **`ModelJudge` has met a real checkpoint, and what it found is fixed.** On
  16 Oct it scored 17 of 18 samples, mean 16.53/25, and refused three at
  character 29 of the completion — the value slot of the first dimension in its
  own instruction template. The checkpoint was echoing the template back. Two
  independent changes landed on 26 Oct:

  - the template is gone from `_ASK`, so a verbatim echo has no balanced object
    to extract, and a test asserts `objects_in(rendered) == []`;
  - `score` now tries every top-level object **last to first**, so one
    unparseable trailing object no longer refuses the sample — and a refused
    sample is what burns a whole run.

  The instruction is hashed into `judge_model_version` by `ask_sha()`, pinned
  *before* that edit, so a run scored either side of it is distinguishable.
  **Re-measure the failure rate on a throwaway copy before spending week 1**;
  that number, not this paragraph, is what makes step 4 safe.
- **Payloads are retained as of 27 Oct**, in `Reasoner.complete`. Before that
  `model_call_payloads` had never held a row: the inserter had no caller, so
  the six nights already run are unreadable and the 16 Oct judge failure could
  not be diagnosed beyond a character offset. **This session is the first time
  that table is exercised on real data** — check it holds rows, and check
  `eval_results.output_path` is not NULL, because both are new.
- **ADR 0015** makes the judge the local reasoner under `local-only`, because
  ADR 0010 had made a cloud judge impermissible since 2 Sep. The policy is a
  constant in `evals/__main__.py`, not configuration, deliberately. Do not
  make it configurable to get a run through.
- **`config/evals/threshold.md`**, fixed 23 Sep while nothing had been scored.
  The verdict prints its content hash beside the number. Do not edit it.
- **The curve refuses ten ways.** Different rubrics, judges, prompt sets; a run
  never scored; a run scored incompletely; a synthetic run; the same brain on
  both sides; an unrecorded generator; a changed model; a changed agent prompt.
  A refusal is the curve working. Read the message and fix the cause.
- **`python -m secondshift.ops`** — `backup`, `verify`, `restore`,
  `night-status`, `doctor`.
- **`deploy/spark/`** holds every unit, including
  `second-shift-backup.user.service` and `second-shift-reasoner.user.service`.
  The reasoner is already on its unit as of 16 Oct;
  `docs/operations/SUPERVISING_THE_REASONER.md` is the record of how, and its
  step 2 trap was real — the unit removes one container while another is still
  serving the port the probe checks, so a naive switch fails every fifteen
  seconds while the reasoner looks healthy.
- **`deploy/judge/Dockerfile`** was built for the first time on 16 Oct, on
  that machine, so the image is `arm64`. It needs a cross-build before it is
  deployed anywhere else, and the demo night it serves returns
  `outcome: null` — a judge opening it sees a night that never finished.
- 11 gates <!-- derived: matches scripts/gate.py ^    \(" --> in
  `scripts/gate.py`, 25 mutations <!-- derived: matches scripts/check-mutations.py ^    Mutation\( -->
  in `scripts/check-mutations.py`. The pre-push hook runs the gate;
  `git config core.hooksPath .githooks` enables it in a fresh clone.

## What the 16 Oct session already closed — do not redo any of it

`ops doctor` (8/8), a backup onto the NAS, a restore of the real data
(byte-identical, 0.174 s), the reasoner onto its unit and off `0.0.0.0`, the
judge container built for the first time, and `ModelJudge` against the real
checkpoint. The evidence for each is in that session's report. `SPEC_ROADMAP.md`
and `RECOVERY.md` have the struck rows.

Two things it left on that machine that are worth knowing: `~/second-shift-src`
is a session clone with its own virtual environment, and
`~/second-shift-restore-test` is a throwaway that is safe to delete. The
`~/judge-probe*-completions.txt` files hold real model output and **must stay on
that machine.**

## Do these in this order, and stop at the first one that fails

Each step's output is the next step's precondition. The order is not a
preference, and step 3 before step 4 is the whole protection on the one
artifact that cannot be remade.

0. **Deploy.** The machine is serving `308e18a`. The judge fix and payload
   retention are both newer than that, and **scoring before deploying scores
   with the instrument that failed.** `deploy/spark/deploy.sh` takes a backup
   before it replaces the tree and runs `doctor` at the end.
1. **`ops doctor`.** Cheap, and the first thing worth knowing after a deploy.
   It subsumes `config show` and it is the only check that looks at data
   ownership — which exists because a service running as the wrong account has
   already corrupted the write-ahead log on that machine. **It now resolves one
   more setting**, `SECOND_SHIFT_PAYLOADS`, which is required: if it is
   unresolved, `doctor` fails on configuration and says so.
2. **The smoke test, on a throwaway copy of the database.** Not the real one.
   `cp` the database aside, record a baseline against it, score it, and read
   three things:
   - **how many samples the judge refused.** On 16 Oct it was 1 of 18 here and
     2 of 5 on the real run. If it is 0 of 18 now, the fix holds and step 4 is
     worth its risk. If it is not, **stop and report that** — it is a finding
     about the instrument, not a reason to loosen the parse.
   - **whether `model_call_payloads` holds rows.** First exercise on real data.
     `SELECT count(*) FROM model_call_payloads` and open one of the files.
   - **whether `eval_results.output_path` is populated.** It was NULL for all
     17 samples on 16 Oct, which is why nobody can read what was scored.
3. **A backup, immediately before touching the real database.** Not the nightly
   one — a fresh one, taken now. **A restore is the only retry that does not
   violate append-only**, it was proven at 0.174 s on that machine, and step 4
   is the step that can destroy something. This is also the first backup that
   carries the payload tree, so check the printed `payloads` count.
4. **Both eval runs, on the real database, in one sitting.** Same judge, same
   model, same agent prompt, two brain states.

   **Order matters and the reason is not obvious.** Record and score the *later*
   baseline first: its brain is reproducible — the brain cannot move while no
   night is queued — so a burned run costs a re-record and nothing else. Score
   the **week-1 baseline last**, because `eval_results` is
   `UNIQUE(eval_run_id, eval_prompt_id, sample_index)` and `score` regenerates
   rather than tops up, so one lost sample burns that run permanently and the
   week-1 brain state cannot be retaken.

   ```bash
   python -m secondshift.evals status
   python -m secondshift.evals baseline --week-of <this week's Monday>
   python -m secondshift.evals score <the new run id>
   python -m secondshift.evals score 01M1FYFECEXC5ZJEWHNP7WZMXB
   python -m secondshift.evals curve
   ```

   `01M1FYFECEXC5ZJEWHNP7WZMXB` is the week-1 baseline and is **untouched**.
   `01M53FX6MV5D9ZWF4Z6117YVSE` is the 16 Oct week-8 baseline and is **burned**:
   three results recorded, still reading `awaiting-scoring` because the process
   was killed before the closing `UPDATE`, un-rescorable because of that UNIQUE
   constraint. Do not try to reuse it. A fresh baseline costs nothing.

   The rubric on disk still hashes to `b4decd6fe774`, which is what the week-1
   baseline pinned, so `score` will not refuse on rubric mismatch — verified
   from the repository on 27 Oct. If it does refuse, something edited the
   rubric and that is the finding.
5. **One real night**, which closes
   `2026-09-17-the-night-revises-what-it-believes` at 7/7. Needs an idea queued,
   and there were none on 16 Oct. Its payloads will be the first a night ever
   retained.
6. **A reboot**, with the API, brain sync and reasoner serving afterward.
   `docs/operations/RECOVERY.md`. The one item the last session could not do,
   and it has to be done from the machine.
7. **`docs/SUBMISSION.md` from the rows that now exist** — the measured table
   rewritten from what step 4 printed, and the claims that stayed unrun struck
   rather than softened. The document already names its own unrun rows.

## The open decision — and it is not yours to make alone

**Whether a Nebius credential may live anywhere but that machine.**

Both endpoints answer from a cloud session — `api.studio.nebius.com/v1/models`
returns 401, `api.eu-north1.nebius.cloud` resolves and answers. So the Nebius
rows are blocked on a *key in the place the work is being done*, not on a route
to the machine. `docs/SPEC_ROADMAP.md` said "none of these closes from a cloud
development session" until 10 Oct, and that was the wrong word.

The Token Factory key is an API key. The Cloud IAM credential is an RS256
private key, and it is a different kind of thing to copy.

**Do not decide this by convenience and do not copy a key to get a run
through.** Put the question to the subject with both options costed: the two
unrun Nebius rows against moving a credential off the machine that was chosen to
hold it. Record the answer wherever it lands, including if the answer is that
the rows stay unrun.

## What good looks like

- Every step above either produced evidence or produced a recorded reason it
  did not. **Eight attempted and five evidenced beats five attempted.**
- The eval curve printed a verdict, or printed a refusal whose cause is written
  down. **A refusal is a result.** "Both runs pin the same brain state" means
  the brain did not move and that is the finding.
- `docs/SUBMISSION.md`'s measured table has numbers where it had **not run**,
  and still says **not run** where nothing ran.
- `python3 scripts/gate.py` green on the machine, not only here. It has still
  never been run there, and the 16 Oct session recorded why it cannot be in
  full: no Chrome for the browser gate, no `openspec` CLI for the specs gate.
  **Run what does run and say which gates were skipped** — that is a result,
  and "the gate has never run there" has been an open row for six weeks.

## Scope — what NOT to build

- **No new capability.** Derive the days left before deciding anything; the
  unshipped list has been longer than the time since 11 Oct.
- **No loosening of a refusal to get a number.** Not the judge's parse, not the
  curve's ten refusals, not the airlock's policy constant. Every one of them was
  added because the alternative was a wrong number that reads like a right one.
- **No stub executor.** `NEBIUS_EXECUTOR.md`'s first hard stop, and the reason
  is in `docs/SUBMISSION.md`: a stub writing plausible job rows is
  indistinguishable from the fan-out that is the entire evidence for the Nebius
  claim.
- **No ASR** until everything above is done.

## Constitution hooks

- **Principle 2.** The eval judge runs `local-only` by ADR 0015 and ADR 0010.
  Nothing in this session may send brain-derived text to a remote provider, and
  the `model_calls` CHECK will refuse it at the database if anything tries.
- **Principle 5.** `is_synthetic` is server-derived. The judge container is the
  same code with a profile and seeded data, never a branch.
- **Principle 7.** Every call this session makes writes telemetry, including the
  throwaway smoke test. If a run is thrown away, throw away its database, not
  its rows.

## The loop

```bash
git status --short && openspec list && openspec list --specs
python3 scripts/gate.py
```

**One command, and it is the one CI runs.** 11 gates <!-- derived: matches scripts/gate.py ^    \(" -->
in order, stopping at the first failure with that gate's exit code. About four
minutes. `docs/development/GATES.md` has the table and the clean-clone
bootstrap.

Never `uv run` on the Spark: it re-resolves the environment to x86_64 and
destroys it.

## Hard stops

Stop, record the question with your recommendation, and move on:

- A `[NEEDS CLARIFICATION]` marker. Do not answer your own.
- A constitution violation. Blocking, not advisory.
- The credential question above.
- Anything in `NOT_BUILDING.md`.
- A refusal you are tempted to relax.

## How to hand the report back

**Push it, do not paste it.** A session on the machine, or on the laptop driving
it, runs somewhere its findings are invisible to whoever asked — and relaying by
hand works once, not for a sequence, and the endgame is a sequence.

```bash
git checkout -b reports/$(date +%F)-machine-session
# write docs/operations/reports/$(date +%F)-machine-session.md
git add docs/operations/reports/ && git commit && git push -u origin HEAD
```

`docs/operations/reports/README.md` is the contract. The short version:
one file, a branch rather than the trunk, placeholders always, and **say what
did not work** — a refusal, a missing file, an unreachable reasoner and a step
not attempted are all findings.

`.githooks/pre-push` runs the two source checks on a report-only push and not
the suites, so this needs git and bash rather than a web toolchain. The
exemption is scoped by path and refuses the moment the push touches anything
else; a mutation holds it to that. Do not reach for `--no-verify`.

## Report

1. Which of the eight steps produced evidence, and what the evidence was.
2. The eval result — the verdict and its standard error, or the refusal and its
   cause. **If the brain did not move, say that.** Name both run ids and the
   week each one is.
3. **The judge's refusal rate against the real checkpoint, as a fraction.**
   This is the number the last session stopped over, and whether the 26 Oct fix
   moved it is the single most useful thing this report can say. If any sample
   still failed, quote the error and the offset.
4. **What `model_call_payloads` holds**, as a count and a sample path — never
   the content, which `reports/README.md` forbids and which is the whole point
   of the table. And whether `eval_results.output_path` is populated.
5. Which rows in `docs/SUBMISSION.md` changed from **not run** to a number, and
   which did not.
6. The credential question, with your recommendation and what each answer costs.
7. What you would do with the remaining days, and why that rather than the
   alternative.
