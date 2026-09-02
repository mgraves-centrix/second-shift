# Add `artifacts` — files you can open, and the outcomes that score them

## Scale classification

**L3 — Epic.** Introduces the on-disk contract every later capability reads
(`morning-interview` presents artifacts, `judge-mode` ships them, `submission`
argues from `cost_per_accepted_artifact`), writes the two tables that make that
view return a number, and is the substitution point `nebius-executor` replaces.
Design doc included.

## Why

"Idea in, artifact out, memory in between" is the scope boundary, and the middle
term does not exist. `night-pipeline` shipped on 2 Sep and can walk six stages;
nothing lands a file anyone can open.

Verified against the tree, not quoted:

- `artifacts` has a writer (`Repository.insert_artifact`) used **only** by
  `packages/seed/`. Nothing in the runtime path writes a row.
- `outcomes` has **no writer at all** — it appears in `repository.py` only in the
  append-only table list.
- `cost_per_accepted_artifact` counts `o.label = 'keep'`. With nothing writing
  `outcomes`, its `accepted` is always 0 and `usd_per_accepted` always NULL. The
  chart the submission's thesis rests on cannot return a number today.

## The first open decision — where artifacts live on disk

`path` is a column, not a layout. The seed already writes paths, and they are the
wrong shape to adopt:

```
artifacts/{night_of}/{kind}.md              # the seed's brief
artifacts/{night_of}/build-{index}/index.html
```

**Two entries worked on the same night collide.** Both write
`artifacts/2026-09-02/brief.md`. The seed gets away with it because it writes
rows, not files — nothing ever opens those paths. A real writer would silently
overwrite one entry's brief with another's.

**The layout:**

```
<root>/<night_of>/<run_id>/brief.md
<root>/<night_of>/<run_id>/research-digest.md
<root>/<night_of>/<run_id>/critique.md
<root>/<night_of>/<run_id>/summary.md
<root>/<night_of>/<run_id>/mockup/<index>/index.html
<root>/<night_of>/<run_id>/build/<index>/...
```

- **`run_id` is the uniqueness key**, not the entry, because a re-run of the same
  entry on a later night must not overwrite what the first night produced. Runs
  are what the timeline and the cost views are keyed on already.
- **`night_of` is the first level** so a human can `ls` a date. The product is
  "what did it do last night," and a directory nobody can navigate by hand is the
  opaque store the constitution forbids in a different format.
- **`path` in the database is stored relative to the root.** The root moves
  between deployments; a stored absolute path would pin the personal instance's
  home directory into rows a judge reads, and `scripts/check-no-environment.sh`
  exists because that has happened before.
- **The root is `SECOND_SHIFT_ARTIFACTS`**, defaulting beside the database. This
  is the fourteenth `SECOND_SHIFT_*` variable, and `configuration`'s enumeration
  test will fail until it is registered — which is that capability working as
  intended rather than an inconvenience.

**Why this works for the judge instance:** it runs the same code with a different
root and `is_synthetic = 1` throughout. Nothing about the layout assumes real
data, and no path element carries anything personal — a run id is a ULID and a
night is a date. Principle 5 is satisfied by configuration, not by a branch.

## The second open decision — what a rank means

**This one cannot be answered here, and faking it would be the exact failure the
prompt warns about.**

The question is whether a rank is trustworthy when the same model family
generates and judges. Answering it requires generating five real variants and
reading them. **The Spark has been unreachable since 2 Sep.** Variants generated
against the `cloud` profile's `EchoReasoner` are placeholders; ranking them
measures nothing, and a comparison written from them would be untrustworthy
evidence dressed as a finding.

**What ships instead:** the machinery, with the *structure* verified —

- `variant_group`, `variant_index` and `variant_rank` are three distinct things
  and never conflated. The test asserts rank is not a copy of index, against the
  synthetic night whose ranks are a shuffled permutation for exactly this reason.
- A rank is written only where a critic actually produced an ordering. **An
  absent critic leaves `variant_rank` NULL** rather than defaulting to the
  generation order, because a rank that is really the generation order is on the
  never-ship list.

**Recommendation, recorded for the subject rather than acted on:** until the
comparison is run, treat `variant_rank` as *the critic's opinion*, not as
ground truth — and specifically, do **not** let it select which variant an
outcome defaults to. `cost_per_accepted_artifact` counts `label = 'keep'`, which
is a human judgement, so the chart stays honest even while the rank is unproven.
The moment rank starts choosing what gets kept, the chart begins measuring the
critic.

## Constitution compliance

| Principle | Outcome | Why |
|---|---|---|
| 1. Brain plaintext under git | **Not implicated** | Artifacts are not the brain. `distill` writes the brain; this writes work products, which are deliberately outside the brain repository — a build directory in a memory repo would drown the diff the eight-week comparison reads. |
| 2. Privacy Airlock | **Constrains** | An artifact is written from a completed stage's output, which already passed the airlock at the model call. No new egress path; the writer touches the local filesystem only. |
| 3. No empty mornings | **Constrains** | Each artifact is written and recorded as its stage completes. A fan-out where one variant's failure loses the other four is the named violation; three of five variants present three. |
| 4. Text-first | **Not implicated** | No speech path. |
| 5. One codebase, two deployments | **Constrains, and the layout is the mechanism** | The judge instance differs by root and `is_synthetic`, both configuration. No `if DEMO_MODE`, and no path element carries anything personal. |
| 6. Scope boundary | **Compliant — and this is the one to watch** | Checked against both `NOT_BUILDING.md` tables. An artifact has a path, a kind and an outcome; adding a status, an assignee or a due date would make it task management, which is on the Excluded table. **"Autonomous execution of generated code" is also Excluded: this produces a build and never runs it, not even to check it compiles.** |
| 7. Telemetry from line one | **Constrains** | Every artifact names its producing invocation. `cost_per_accepted_artifact` already filters `is_synthetic = 0` on both runs and artifacts; the outcome writer carries the flag so seed outcomes cannot enter it. |

No violations.

## Non-goals

- No Nebius fan-out. This defines what a variant is; `nebius-executor`
  substitutes parallel dispatch for the sequential loop.
- No in-app editing, no outcome-capture UI, no new artifact kinds.
- **Nothing executes a generated build**, including as a validity check.
- No artifact deletion or retention policy. Tables are append-only and files are
  not; a retention story needs a decision about what "the artifact for this run"
  means after a cleanup, and guessing it here would be worse than not having one.
  Recorded in tasks.
