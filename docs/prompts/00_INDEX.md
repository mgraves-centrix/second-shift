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
   API_LAYER ──────┐   (run early: it de-collides four later sessions)
   CONFIGURATION ✅┤
                   ├──> NIGHT_PIPELINE ✅> ARTIFACTS ──┐
   AGENTS ────────✅┘        │                         ├──> JUDGE_MODE ──> SUBMISSION
                             ├──> RESEARCH ────────────┤                      ^
   RETRIEVAL ───────────────✅┘                        │                      │
                                                       │       EVAL_SCORING ──┘
   FRONTEND ──> MORNING_INTERVIEW ─────────────────────┘

   ✅ shipped 2 Sep. ARTIFACTS and RESEARCH are now the unblocked ones.

   TEST_HARNESS    OPERATIONS    ASR    NEBIUS_EXECUTOR
   any time        needs the     needs  blocked on
                   machine       Spark  credentials
```

Shipped rows are struck through. A prompt for a shipped capability is a record
of what was asked, not a session to run — read it for the reasoning, and read
the change in `openspec/changes/archive/` for what actually happened, which in
all three cases differs from the prompt in at least one decision.

| # | Prompt | Owns | Runs after | Parallel with |
|---|---|---|---|---|
| 0 | `API_LAYER.md` | `api/`, `api/app.py` | — | 8, 10 |
| 1 | ~~`CONFIGURATION.md`~~ | ✅ shipped 2 Sep | — | — |
| 2 | ~~`AGENTS.md`~~ | ✅ shipped 2 Sep | — | — |
| 3 | ~~`RETRIEVAL.md`~~ | ✅ shipped 2 Sep | — | — |
| 4 | ~~`NIGHT_PIPELINE.md`~~ | ✅ shipped 2 Sep | — | — |
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
| — | `ASR.md` | `providers/asr*`, spike F | — | everything |

**Three collision surfaces, not two.** Two sessions must never both be in
`apps/web/app/`, in `secondshift/night/`, or in **`api/app.py`** — which is a
single 368-line file that five of these sessions need to add routes to.

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
| Eval baseline | 2 Sep — `01M1FYFECEXC5ZJEWHNP7WZMXB`, six prompts, rubric `b4decd6fe774`, brain `ad17b3bcddb6`, **awaiting scoring** |
| Entries | 2 Sep — 4 real: 1 archived, **3 still queued and never processed** |
| Runs | 2 Sep — **0.** No night has ever executed |
| Production code | 2 Sep — deployed tree dated 30 Aug; `retrieval`, `agents` and the embedder are **not** on the machine |
| Reasoner | 2 Sep — container up, but **unmanaged**: the systemd unit was never installed, so a reboot ends it |
| API / brain sync | 2 Sep — both live as enabled user units |

**Nothing reasons in production.** `local-inference` and `agents` both shipped,
and a real completion was made through an agent from a development window — but
the deployed code predates all of it, and `model_calls` on the machine is still
empty. The gap is a deploy, not a missing capability.

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
4. **`docs/NEBIUS_USAGE.md` does not exist.** `SUBMISSION.md` still lists it as a
   deliverable and describes what it has to argue; it was a day-7 item and did
   not happen. `ARCHITECTURE.md`'s directory tree used to assert it as a file on
   disk — that entry is gone, because a tree is not the place to record an
   intention.
5. **The API layer had no owner**, and `api/routes/` — which
   `ARCHITECTURE.md`'s directory tree asserted — does not exist. The real
   package is `secondshift/api/`, a flat set of modules with `app.py` at 368
   lines. The tree now says that instead.
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
