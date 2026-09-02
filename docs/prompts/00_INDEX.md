# Session prompts — the development layers

One file per session. Paste as the first message of a fresh session; each is
self-contained on purpose, so the shared sections repeat rather than referring
you elsewhere.

**Deadline: Fri 30 Oct 2026, 10:00 PT.** Solo. Written 2 Sep, which leaves 58
days.

---

## The sequencing rule

**Parallelize by new surface; sequence by shared surface.** Two sessions may run
at once only if the set of files they write is disjoint. Everything below is
grouped by that rule, not by how interesting it is.

```
   API_LAYER ──────┐   (run early: it de-collides five later sessions)
   CONFIGURATION ──┤
                   ├──> NIGHT_PIPELINE ──> ARTIFACTS ──┐
   AGENTS ─────────┘         │                         ├──> JUDGE_MODE ──> SUBMISSION
                             ├──> RESEARCH ────────────┤                      ^
   RETRIEVAL ────────────────┘                         │                      │
                                                       │       EVAL_SCORING ──┘
   FRONTEND ──> MORNING_INTERVIEW ─────────────────────┘

   TEST_HARNESS    OPERATIONS    ASR    NEBIUS_EXECUTOR
   any time        needs the     needs  blocked on
                   machine       Spark  credentials
```

| # | Prompt | Owns | Runs after | Parallel with |
|---|---|---|---|---|
| 0 | `API_LAYER.md` | `api/routes/`, `api/app.py` | — | 1, 2, 3, 8, 10 |
| 1 | `CONFIGURATION.md` | `config.py`, `config/*.toml` | — | 0, 2, 3, 8, 10 |
| 2 | `AGENTS.md` | `secondshift/agents/` | — | 0, 1, 3, 8, 10 |
| 3 | `RETRIEVAL.md` | `retrieval/`, `providers/embed*` | — | 0, 1, 2, 8, 9 |
| 4 | `NIGHT_PIPELINE.md` | `night/`, `repository.close_run` | 1, 2 | 9, 10 |
| 5 | `RESEARCH.md` | `research/`, `providers/tavily*` | 3, 4 | 6 |
| 6 | `ARTIFACTS.md` | `secondshift/artifacts/` | 4 | 5 |
| 7 | `NEBIUS_EXECUTOR.md` | `providers/nebius*`, ingest route | credentials | anything |
| 8 | `FRONTEND.md` | `components/`, `app/globals.css` | — | 0, 1, 2, 3, 10 |
| 9 | `MORNING_INTERVIEW.md` | `app/morning/`, `secondshift/morning/` | 8 | 4, 10 |
| 10 | `TEST_HARNESS.md` | `.github/`, `scripts/gates/` | — | everything |
| 11 | `JUDGE_MODE.md` | `deploy/judge/` | 4, 6, 9 | 12 |
| 12 | `EVAL_SCORING.md` | `eval_runs` rows, the curve | a judge | 11 |
| 13 | `SUBMISSION.md` | `docs/NEBIUS_USAGE.md`, the write-up | 11, 12 | — |
| — | `OPERATIONS.md` | `deploy/`, the machine | — | everything |
| — | `ASR.md` | `providers/asr*`, spike E | — | everything |

**Three collision surfaces, not two.** Two sessions must never both be in
`apps/web/app/`, in `secondshift/night/`, or in **`api/app.py`** — which is a
single 368-line file that five of these sessions need to add routes to.

That third one was missed when this index was first written, and it is the reason
`API_LAYER.md` exists and should run early: it splits the file into
`api/routes/` as `docs/ARCHITECTURE.md` already specifies, after which adding a
route touches one new file and the five sessions stop queueing behind each other.

---

## What is true on 2 Sep — do not re-derive any of it

Verified on the machine, not inferred from the repository.

| | |
|---|---|
| Suite | 302 Python tests, 25 web tests, typecheck, both check scripts — green |
| Capabilities | 10 shipped: persistence, telemetry, compute-profiles, privacy-airlock, capture, brain, evals, synthetic-seed, local-inference, night-timeline |
| Reasoner | **live** — `nemotron-3.5-lightning` on the Spark, 65k context, container up |
| API | **live** — uvicorn on 127.0.0.1:8080 as a user service; linger enabled |
| Brain sync | **live** — timer firing |
| Eval baseline | recorded 2 Sep: `01M1FYFECEXC5ZJEWHNP7WZMXB`, six prompts, rubric `b4decd6fe774`, brain `ad17b3bcddb6`, awaiting scoring |
| Entries | 4 real — 1 archived, **3 still queued and never processed** |
| Runs | **0.** No night has ever executed |

**Nothing reasons yet in production.** `local-inference` implements `Reasoner`
and the registry binds it, but no agent calls it, because there are no agents.

---

## The gaps nobody had a plan for

Found 2 Sep. Each is now a prompt above.

1. **`configuration`** — ten `SECOND_SHIFT_*` variables across three TOML files,
   no way to print the resolved configuration or where each value came from.
2. **`agents`** — `docs/ARCHITECTURE.md` specifies `agents/ roster + versioned
   prompt files`. The directory does not exist. `agents.prompt_sha` is `NOT NULL`
   and the only thing writing it is a test fixture writing `deadbeef`.
3. **`close_run` has no caller.** Every run is permanently in flight, with a null
   outcome and no end time. `night-timeline` reads around it.
4. **`docs/NEBIUS_USAGE.md` does not exist.** `ARCHITECTURE.md` calls it "evidence
   doc for the judging criterion." It was a day-7 deliverable and did not happen.
5. **The API layer had no owner**, and `api/routes/` — specified in
   `ARCHITECTURE.md`'s own directory tree — does not exist.
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
