# Session prompts — the development layers

One file per session. Paste as the first message of a fresh session; each is
self-contained on purpose, so the shared sections repeat rather than referring
you elsewhere.

**Deadline: Fri 30 Oct 2026, 10:00 PT.** Solo.

A day count was written here on 2 Sep and was wrong by two weeks the next time
anyone read it. Derive it instead — `python3 -c "from datetime import date;
print((date(2026,10,30) - date.today()).days)"` — because a number that ages is
worse than no number: it reads as current.

---

## The sequencing rule

**Parallelize by new surface; sequence by shared surface.** Two sessions may run
at once only if the set of files they write is disjoint. Everything below is
grouped by that rule, not by how interesting it is.

```
   API_LAYER ─────✅┐
   CONFIGURATION ✅┤
                   ├──> NIGHT_PIPELINE ✅> ARTIFACTS ✅┐
   AGENTS ────────✅┘        │                         ├──> JUDGE_MODE ✅> SUBMISSION
                             ├──> RESEARCH ✅─────────┤                      ^
   RETRIEVAL ───────────────✅┘                        │                      │
                                                       │       EVAL_SCORING ──┘
   FRONTEND ✅> MORNING_INTERVIEW ✅────────────────────┘        curve ✅
                                                                scoring needs
   TEST_HARNESS ✅ OPERATIONS ✅  ASR    NEBIUS_EXECUTOR         a judge
                                 needs  a credential, which
                                 Spark  is on the machine
```

**✅ shipped. Everything unshipped is waiting on the same thing.** `ASR`,
`NEBIUS_EXECUTOR`, the scoring half of `EVAL_SCORING`, and the verification half
of `OPERATIONS` and `JUDGE_MODE` all need the always-on machine — for a model,
for a credential that is on it, for a reboot, or for a container runtime.
`docs/SPEC_ROADMAP.md`'s "Owed verification" section is the one list of what a
session there owes, and it is where to look before opening any of these.

Shipped rows are struck through. A prompt for a shipped capability is a record
of what was asked, not a session to run — read it for the reasoning, and read
the change in `openspec/changes/archive/` for what actually happened, which in
all three cases differs from the prompt in at least one decision.

| # | Prompt | Owns | Runs after | Parallel with |
|---|---|---|---|---|
| 0 | ~~`API_LAYER.md`~~ | ✅ shipped 21 Sep — nine routes in five modules under `api/routes/` | — | — |
| 1 | ~~`CONFIGURATION.md`~~ | ✅ shipped 2 Sep | — | — |
| 2 | ~~`AGENTS.md`~~ | ✅ shipped 2 Sep | — | — |
| 3 | ~~`RETRIEVAL.md`~~ | ✅ shipped 2 Sep | — | — |
| 4 | ~~`NIGHT_PIPELINE.md`~~ | ✅ shipped 2 Sep | — | — |
| 5 | ~~`RESEARCH.md`~~ | ✅ shipped 2 Sep | — | — |
| 6 | ~~`ARTIFACTS.md`~~ | ✅ shipped 2 Sep | — | — |
| 7 | `NEBIUS_EXECUTOR.md` | `providers/nebius*`, the poller's telemetry collection | a credential, which lives on the machine | anything |
| 8 | ~~`FRONTEND.md`~~ | ✅ shipped 3 Sep | — | — |
| 9 | ~~`MORNING_INTERVIEW.md`~~ | ✅ shipped 3 Sep — server half and `app/morning/` | — | — |
| 10 | ~~`TEST_HARNESS.md`~~ | ✅ shipped 17 Sep — `scripts/gate.py`, CI | — | — |
| 11 | ~~`JUDGE_MODE.md`~~ | ✅ shipped 20 Sep — `deploy/judge/`. The container has never been built; that needs a machine with a container runtime | — | — |
| 12 | `EVAL_SCORING.md` | the week-8 run. **The curve shipped 21 Sep** | a judge, which needs Token Factory | — |
| 13 | `SUBMISSION.md` | the write-up. **`docs/NEBIUS_USAGE.md` was written 21 Sep**, with three claims marked not yet run and the query for each | 12 | — |
| — | ~~`OPERATIONS.md`~~ | ✅ shipped 21 Sep — `python -m secondshift.ops`. The reboot and the on-machine restore are owed | — | — |
| — | `ASR.md` | `providers/asr*`, spike F | — | everything |
| — | `ENDGAME.md` | the order of what is left, and the machine session in full | — | nothing: it runs first |
| — | `MACHINE_SESSION_OPENER.md` | nothing. It is the text you paste to start a local session against the machine, and it points at `ENDGAME.md` rather than restating it | — | — |

**`ENDGAME.md` is the one file here that is not one session.** It owns the
ordering of the rest and the full prompt for the machine session, because that
session unblocks everything else and the week-8 eval window — **Thu 15 to Wed
21 Oct** — closes before the deadline does. Start there.

**Two collision surfaces now, and the third is closed.** Two sessions must never
both be in `apps/web/app/` or in `secondshift/night/`.

The third was `api/app.py`, a single file five sessions needed to add routes to:
368 lines when this was written, 473 on 19 Sep, 539 on 21 Sep. `api-layer`
shipped that day and it is 80 lines <!-- derived: lines apps/api/secondshift/api/app.py --> with no route in it; a route now lives in
`api/routes/<capability>.py` and adding one touches one file, measured rather
than asserted. Three of the five sessions ran in sequence before the split and
paid the cost, so the scheduling argument was largely spent by the time it
landed — recorded because it is the second time this index's own ordering advice
was right and ignored.

That third one was missed when this index was first written, and it is the reason
`API_LAYER.md` exists and should run early: it splits the file into
`api/routes/` as `docs/ARCHITECTURE.md` already specifies, after which adding a
route touches one new file and the five sessions stop queueing behind each other.

---

## What is true — derive it, do not read it here

This section used to be a table of numbers headed "do not re-derive any of it."
Every derivable number in it was wrong within a day: it claimed 302 tests
against 358, and ten capabilities against twelve. The instruction not to
re-derive is what made the staleness durable, so the numbers are gone and the
commands that produce them are here instead.

```bash
apps/api/.venv/bin/python -m pytest apps/api/tests -q   # suite
npm --prefix apps/web run test                          # web
openspec list --specs                                   # capabilities
openspec list                                           # active changes
```

**What cannot be derived from the repository** — because it lives on the
always-on machine — is below, with the date it was read. Treat every line as a
claim whose age you can see.

| | read |
|---|---|
| Eval baseline | 16 Oct — `01M1FYFECEXC5ZJEWHNP7WZMXB` **untouched and still unscored**, which was deliberate; see the stopped run below |
| Scoring | 16 Oct — `ModelJudge` ran against the real checkpoint: 17 of 18 samples scored, mean 16.53/25. The run started for the curve was **stopped on purpose** after three refusals at one offset, and that run id is burned. The baseline was not spent. |
| Entries | 16 Oct — **0 queued.** The real entries have been processed; a night needs an idea queued and there was none |
| Runs | 16 Oct — **six real nights have executed.** Their payloads were not retained, because nothing wrote to `model_call_payloads` until 27 Oct |
| Database | 16 Oct — 219 rows across 17 tables, schema 3, 39 artifact files |
| Production code | 16 Oct — redeployed at `308e18a`, API serving. `secondshift.ops` was **absent** from the tree before that deploy, so no backup had ever been possible |
| Reasoner | 16 Oct — **on its systemd unit**, and moved off `0.0.0.0` to `127.0.0.1:8200` |
| Backups | 16 Oct — four on the NAS, under `scratch`, which exports no backup share |
| Judge container | 16 Oct — **built for the first time**, `arm64`, needs a cross-build before it is deployed anywhere |
| API / brain sync | 16 Oct — both live as enabled user units |

**Production reasons now.** This paragraph read "Nothing reasons in production"
and "`model_calls` on the machine is still empty" until 27 Oct, on the strength
of a 2 Sep reading — which was correct then and had been wrong for six weeks by
the time anybody re-read it. **The claim is not that the table was wrong; it is
that a table of dated claims still has to be re-read.** The dates above are
from `docs/operations/reports/2026-10-16-machine-session.md`, which is where
every line of them comes from.

---

## The gaps nobody had a plan for

Found 2 Sep. Each is now a prompt above.

1. ~~**`configuration`**~~ — **closed 2 Sep** (`2026-09-02-add-configuration`).
   Thirteen `SECOND_SHIFT_*` settings, each reporting the layer it resolved
   from. The count was the whole lesson: this line said *ten* until 2 Sep while
   `retrieval` had already added three, so the capability now carries a test that
   scans the tree — Python and shell both — and fails when the registry falls
   behind. Do not trust a count in a document; run the scan.
2. ~~**`agents`**~~ — **closed 2 Sep** (`2026-09-02-add-agents`). Six roles, six
   drafted prompt files, `prompt_sha` computed from file content. `deadbeef` is
   gone from the codebase.
3. ~~**`close_run` has no caller.**~~ — **closed 2 Sep**
   (`2026-09-02-add-night-pipeline`). It also had no test; both are fixed, and
   the refusal-to-double-close its docstring always claimed is now checked. An
   open run means a process died, not the normal case.
4. ~~**`docs/NEBIUS_USAGE.md` does not exist.**~~ **Closed 21 Sep.** The split
   argued from ADR 0004, the rates from `config/pricing.toml`, the per-role
   model bindings, and a status table that marks three claims **not yet run**
   and names the query that will produce each rather than estimating them. It
   was a day-7 item that did not happen, and `ARCHITECTURE.md`'s tree asserted
   it as a file on disk for weeks — that entry went on 16 Sep, because a tree is
   not the place to record an intention.
5. **The API layer had no owner**, and `api/routes/` — which
   `ARCHITECTURE.md`'s directory tree asserted — does not exist. The real
   package is `secondshift/api/`, a flat set of modules with `app.py` at 539
   lines as of 21 Sep. The tree now says that instead.
6. **Nothing produced a week-8 eval score.** `SUBMISSION.md` declares a
   dependency on it. The submission's centerpiece had no owner at all.
7. **Nobody owned the machine.** Four prompts mention deploying; none owns the
   reboot story, the backups, or a recovery procedure anyone has executed.
8. **ASR was deferred to "its own session"** by `MORNING_INTERVIEW.md`, and that
   session did not exist. It gates nothing — principle 4 — but the last unrun
   spike had no home.

---

## How these prompts were graded

Each was scored out of 12 before being committed. A prompt that scores below 9.9
was rewritten, not shipped with a caveat.

| # | Criterion | Fails when |
|---|---|---|
| 1 | Grounded in verified fact | It cites a number nobody measured |
| 2 | Reproduction commands | The reader cannot get to the starting state |
| 3 | Names the open decision | It hides a choice inside prose |
| 4 | Forbids deciding by preference | It says "choose an approach" with no method |
| 5 | Falsifiable success criteria | "Make it good" |
| 6 | Explicit non-goals | Scope is implied rather than bounded |
| 7 | Constitution hooks | The governing principle is unnamed |
| 8 | A runnable loop | A command in it does not work |
| 9 | Verification that can fail | No negative or mutation check |
| 10 | Quality bar specific to this work | Only the generic never/always list |
| 11 | Hard stops | Markers, credentials and destructive acts unaddressed |
| 12 | Report demanding honesty | No "say so if it is not good" |

Scores are in `GRADES.md` beside this file, with the specific weakness that each
rewrite fixed. A grade claimed without a named weakness is not a grade.
