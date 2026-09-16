# Add `night-pipeline` — the checkpointed stage machine

## Scale classification

**L3 — Epic.** Spans the repository, agents, retrieval, the airlock and the
brain; introduces the pattern every later capability reads (`artifacts`,
`morning-interview`, `eval-scoring` all consume what this writes); and makes
constitution principle 3 executable rather than decorative. Design doc included,
per `openspec/config.yaml`.

## Why

Everything shipped so far captures, stores, measures or renders. Nothing has
ever done the work.

Verified against the tree on 2 Sep, not quoted from a document:

- `run_stages` has **no writer** outside `packages/seed/`.
- `Repository.close_run` has **no caller and no test** — the only other mention
  of it in the tree is a comment in `repository.py` noting its own absence. Its
  docstring claims it "refuses to close one that is already closed" and nothing
  has ever checked that.
- Every run the system could record would sit permanently in flight, with a null
  `outcome` and a null `ended_at_ms`.

**What is not verified here:** how many real entries are queued on the always-on
machine, and whether `runs` is empty there. That was read on 2 Sep and the
machine has been unreachable since. This proposal does not depend on it.

## The open decision — which stages block their successors

Not decided by preference. Built from what each stage can actually call **today**,
which is the constraint that settles most rows:

| Available now | Not available |
|---|---|
| `retrieval.assemble_context`, `agents.invoke`, `VllmReasoner`, `BrainRepo.commit_paths` | a Tavily provider (`research` has not shipped), artifact rendering (`artifacts` has not shipped) |

| Stage | Consumes | With that input missing or partial | Blocks its successors? |
|---|---|---|---|
| `brief` | entry text; retrieved context | Entry text cannot be missing — `_ELIGIBLE` already screens `TRIM(raw_text) != ''`. Retrieval unavailable → brief from the entry alone, **and the brief says so**. | **Yes, totally.** It is the root. Nothing downstream has an input without it. |
| `research` | the brief; external sources | **No provider exists.** Skipped every night today, with that as the recorded reason — not failed, because nothing was attempted. | **No.** `mockups` and `build` proceed on the brief. |
| `mockups` | the brief; research if present | Without research: an approach argued from the idea itself. Degraded but real — this is the pair the prompt names. | **No.** `build` can work from the brief alone. |
| `build` | the brief; mockups and research if present | Without mockups: the builder works from the brief. Degraded but real. | **Yes, for `critique` only.** |
| `critique` | build output | Nothing to critique produces nothing useful — the prompt's other named pair, and it holds. | **No.** `distill` still has the earlier stages. |
| `distill` | every stage that reached `complete` | One completed stage is evidence. Zero is not. | — terminal. **Runs when any stage completed, skipped when none did.** |

**Two blocking edges, not a chain:** `brief → everything`, and `build → critique`.
A uniform "each stage blocks the next" rule would have skipped `mockups` and
`build` whenever `research` was unavailable — which is every night today — and
produced empty mornings on exactly the nights principle 3 exists for.

`distill` is the row that resists the shape entirely. It is not blocked by any
single predecessor; it is blocked by *all of them failing*, which is a different
predicate and is why the table is per-stage rather than per-edge.

## The second open decision — what starts a night

**Both, and the manual path ships here.**

- `python -m secondshift.night run` — dispatches every eligible entry. This is
  what runs at 2am when something is wrong.
- `python -m secondshift.night run --entry <id>` — one entry, for debugging.
- A `second-shift-night.user.timer` mirroring the shipped
  `second-shift-brain-sync.user.timer` pattern. **Written, not installed.**
  Installing units on the always-on machine is `operations`' job and needs a
  machine this session cannot reach; a timer this capability claims to have
  enabled would be a claim nobody checked.

## Stage → agent role

The seed has a `_STAGE_ROLES` map, and it is **not** a product decision — its own
comment says the roles were chosen so "the timeline renders distinct lanes." It
assigns `brief` to the **interviewer**, which contradicts ADR 0005 (*the
interview stays in the morning*). The pipeline uses its own map, grounded in what
each shipped prompt says it does:

| Stage | Role | The prompt's own words |
|---|---|---|
| `brief` | `researcher` | "You turn source material into a brief someone can act on. You are given extracts, not a search box." — retrieved context is the extracts |
| `research` | `researcher` | same role, different source, when a provider exists |
| `mockups` | `architect` | "You turn a half-formed idea into a plan someone could build from." |
| `build` | `builder` | "You produce the artifact." |
| `critique` | `critic` | "You rank what the builders produced." |
| `distill` | `distiller` | "You update the brain." |
| — | `interviewer` | "You conduct the morning interview." **No night stage.** ADR 0005. |

A role is a prompt, not a singleton, so `researcher` appearing twice is not a
conflict.

## Where a stage's output lives

`artifacts` has not shipped, so no stage writes a file — except `distill`, which
writes the brain and records `commit_sha` and `committed_at_ms` on its stage row.

Every other stage's output is recoverable from telemetry: the completion text is
already captured through `model_call_payloads`, which the recorder writes. That
is the honest answer, and `commit_sha` stays null on those rows until `artifacts`
gives them a file. A null there means "not yet rendered," not "lost."

## Constitution compliance

| Principle | Outcome | Why |
|---|---|---|
| 1. Brain plaintext under git | **Constrains** | `distill` writes topic files through `BrainRepo.commit_paths`, which stages paths rather than the tree — a hand-edited file is never swept into an automated commit. |
| 2. Privacy Airlock | **Constrains, blocking if wrong** | `resolve_policy` runs once per run, before any provider call, and the resolution is stamped on the row. Where it returns `permitted=False` the run is **quarantined, never downgraded**. Note the trap: `Registry.bind("cloud")` returns an `EchoReasoner`, so a `local-only` entry on a cloud profile would otherwise "succeed" against a placeholder. It is refused before dispatch. |
| 3. No empty mornings | **Governs — this capability is the principle** | Each stage opens, runs and closes in its own transaction. No batch, no all-or-nothing. Proved by killing the process mid-run in a subprocess, not by assertion. |
| 4. Text-first | **Not implicated** | No speech path. |
| 5. One codebase, two deployments | **Constrains** | Provider selection is `Registry.bind(profile)`; the pipeline names no backend. No `if DEMO_MODE`. |
| 6. Scope boundary | **Compliant** | Checked against both tables in `NOT_BUILDING.md`, not asserted. No queue UI, no retry button, no priority field. **"Autonomous execution of generated code" is on the Excluded table** — `build` produces text and never executes it. |
| 7. Telemetry from line one | **Constrains** | Every stage opens an `agent_invocations` row through `Recorder.invocation`; every model call is recorded by the provider base class. A stage that ran and left no trace would be indistinguishable from one that was skipped. |

No violations.

## Non-goals

- No morning interview, no artifact rendering, no research provider, no new
  stages (six, fixed by a database CHECK).
- Nothing executes generated code.
- No reaper for runs killed mid-flight. `close_run` is called on every terminal
  path this process controls; a process that dies leaves an open run, which is
  **correct and visible** rather than silently reconciled. Recorded in tasks as a
  named gap for `operations`, because a reaper that guesses an outcome is worse
  than an open row that is honest.
