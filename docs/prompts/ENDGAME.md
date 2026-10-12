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

## The hard date is not the deadline

Weeks run Thursday to Wednesday from 27 Aug, so **week 8 is Thu 15 Oct to Wed
21 Oct.** The submission's centerpiece is the same fixed prompts scored in week
1 and week 8, and the curve refuses two judges, two models and two agent
prompts as two instruments. That means **both runs are generated and scored in
one sitting, inside that window, with everything pinned identically.**

Miss it and the headline becomes week 1 against week 9, told in a document that
has to explain why. The deadline has slack; the window does not.

## What is left, and the one thing it waits on

Four claims in `docs/SUBMISSION.md` read **not run**, and after 10 Oct they are
no longer one blocker:

| | Needs |
|---|---|
| The week-8 eval score | **The machine only.** ADR 0015 made the judge local, so no credential |
| A real night proposing a belief against the real brain | The machine only. Closes `2026-09-17-the-night-revises-what-it-believes` at 7/7 |
| The judge container built and stood up | A container runtime. The NAS runs containers |
| A build stage fanned out to real parallel Nebius Jobs | A credential, and `nebius-executor` is 3/23 |
| A cloud night's cost beside a local one | The same credential, plus the local night's rows |

`docs/SPEC_ROADMAP.md`'s **Owed verification → Open** table is the authoritative
list and is longer than this one. Read it before starting. Do not re-derive it
here; it moves.

## The order

1. **The machine session.** Everything below. Run it first, and run the eval
   inside it — the generation and the scoring both need the local reasoner, so
   splitting them across sessions buys nothing and risks the window. It runs on
   the machine or over SSH from the laptop; see *Where this session runs*.
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
- **The reboot drops the connection.** Step 8 ends the session that issued it.
  Expect the disconnect, do not read it as a failure, and reconnect to verify
  what came back up rather than inferring it from a command that never
  returned.
- **A real night outlives an SSH session.** Do not run step 7 in the foreground
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
- **`ModelJudge` has never seen a real checkpoint.** Thirteen tests against a
  real socket, every one of them answered by a stub. A stub cannot predict what
  a real model writes around its JSON. **This is the single highest-risk item in
  the endgame** and it is cheap to settle: one `score` run against a throwaway
  copy of the database tells you whether the extraction rule holds.
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
  **Read `docs/operations/SUPERVISING_THE_REASONER.md` step 2 before switching
  the reasoner**: the unit removes one container while another is still serving
  the port the probe checks, so a naive switch fails every fifteen seconds while
  the reasoner looks healthy.
- **`deploy/judge/Dockerfile`** exists and has never been built.
- 11 gates in `scripts/gate.py`, 17 mutations in `scripts/check-mutations.py`.
  The pre-push hook runs the gate; `git config core.hooksPath .githooks` enables
  it in a fresh clone.

## Do these in this order, and stop at the first one that fails

Each step's output is the next step's precondition. The order is not a
preference.

1. **`ops doctor`.** It subsumes `config show` and it is the only check that
   looks at data ownership — which exists because a service running as the wrong
   account has already corrupted the write-ahead log on that machine.
2. **A backup, then `ops verify` it, onto the NAS.** First real test of the
   same-device guard: an unmounted share must fail the unit rather than quietly
   filling the local disk.
3. **A restore of the real data onto a scratch path**, diffed and timed. The
   mechanism is rehearsed against a generated night; that disk and that data are
   not.
4. **The reasoner onto its unit**, gated on `ops night-status`. Step 2 of
   `SUPERVISING_THE_REASONER.md` first.
5. **One `score` run against a throwaway copy of the database.** Not the real
   one. This is the `ModelJudge` smoke test, and a refused judgement here is a
   finding about the prompt, not a reason to loosen the parse.
6. **The week-1 and week-8 eval runs, on the real database, in one sitting.**
   Same judge, same model, same agent prompt, two brain states. Then
   `python -m secondshift.evals curve` and record whatever it says.
7. **One real night**, which closes
   `2026-09-17-the-night-revises-what-it-believes` at 7/7. Needs an idea queued.
8. **A reboot**, with the API, brain sync and reasoner serving afterward.
   `docs/operations/RECOVERY.md`.
9. **The judge container built and stood up**, and read by somebody who has not
   seen it.

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
  did not. **Nine attempted and six evidenced beats six attempted.**
- The eval curve printed a verdict, or printed a refusal whose cause is written
  down. **A refusal is a result.** "Both runs pin the same brain state" means
  the brain did not move and that is the finding.
- `docs/SUBMISSION.md`'s measured table has numbers where it had **not run**,
  and still says **not run** where nothing ran.
- `python3 scripts/gate.py` green on the machine, not only here. It has never
  been run there.

## Scope — what NOT to build

- **No new capability.** Nineteen days, and the unshipped list is already longer
  than the time.
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

## Report

1. Which of the nine steps produced evidence, and what the evidence was.
2. The eval result — the verdict and its standard error, or the refusal and its
   cause. **If the brain did not move, say that.**
3. What `ModelJudge` did against a real checkpoint, in its own words: how many
   samples it refused and what the completions looked like.
4. Which rows in `docs/SUBMISSION.md` changed from **not run** to a number, and
   which did not.
5. The credential question, with your recommendation and what each answer costs.
6. What you would do with the remaining days, and why that rather than the
   alternative.
