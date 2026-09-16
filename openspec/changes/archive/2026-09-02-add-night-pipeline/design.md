# Design — `night-pipeline`

## Context

`run_stages` and `runs` were designed on 27 Aug and have carried the shape of
this capability ever since. `0001_initial.sql:65` says it in a comment:

> Explicit stage table, not a JSON checkpoint blob. "No empty mornings" is a
> query: the morning brief renders whatever stages reached 'complete'.

So the storage decision is made and this design does not reopen it. What is open
is the control flow over it.

## Decision 1 — a stage is a transaction, and the loop owns the boundary

Each stage: insert `run_stages` row as `running`, invoke, then
`complete_run_stage` with `complete`, `failed`, or `skipped`. Three separate
writes, no enclosing transaction across stages.

**Alternatives considered:**

- *One transaction per run, committed at the end.* Rejected — this is principle
  3's named violation in as many words ("an all-or-nothing transaction across
  stages"). It is also the mutation the crash test uses to prove itself.
- *A checkpoint blob updated in place.* Rejected by the schema comment above,
  and separately by the append-only convention: an updated blob loses the
  history of what a stage said before it was retried.
- *Stage functions that commit themselves.* Rejected — six copies of the
  transaction boundary that can drift. The loop owns it; a stage function
  returns a result or raises.

## Decision 2 — blocking is a predicate per stage, not an edge in a chain

The proposal's table has two blocking edges and one stage (`distill`) whose
predicate is over the whole run. Modeling that as edges would have needed a
special case for `distill` anyway.

So each stage carries `can_run(completed: set[str]) -> bool`. `critique` returns
`"build" in completed`. `distill` returns `bool(completed)`. `mockups` and
`build` return `"brief" in completed`. It reads as the table, which is the point:
the table is the specification and the code should be checkable against it by
eye.

**Alternative considered:** a `depends_on: tuple[str, ...]` field with "all must
have completed" semantics. Rejected — `distill` is "any", not "all", so the field
would have needed a mode flag beside it, and a two-field encoding of a
five-line predicate is harder to check against the table than the predicate.

## Decision 3 — quarantine is a refusal before dispatch, not a stage outcome

`resolve_policy` returns `permitted=False` where the profile cannot honor the
policy. The run is then **never opened**: no `runs` row, no stages, no model
calls. The entry stays `queued` and the reason is recorded as a typed failure.

**Alternative considered:** open the run, mark every stage `skipped`, close it
`aborted`. Rejected — it writes a run that never ran, and `runs` is the table the
cost-per-artifact curve is computed over. An aborted run with six skipped stages
would enter that denominator as a night that happened.

The trap this guards is concrete: `Registry.bind("cloud")` returns an
`EchoReasoner` placeholder. Without the refusal, a `local-only` entry on a cloud
profile would run to `complete` against a stub and look like a successful night.

## Decision 4 — a failed stage does not fail the run

Outcome is derived at close time from what the stages did:

| Stages | `runs.outcome` |
|---|---|
| all six `complete` | `complete` |
| any `complete`, any `failed` or `skipped` | `degraded` |
| none `complete` | `failed` |
| refused before dispatch | no run row at all |

`degraded` is the expected outcome of every night today, because `research` has
no provider and is skipped. That is correct and should not be quietly reported as
`complete`: a night that skipped a stage is a night with a gap in it, and the
morning is supposed to be able to say so.

## Decision 5 — the entry returns to `queued` on failure

Already decided by the schema: `_ENTRY_TRANSITIONS` has `running → queued` and
there is no failed state for an entry. This design respects it rather than
adding one. An idea that could not be worked on tonight is an idea to work on
tomorrow.

Idempotence follows from the same place: `dispatch_eligible_entries()` screens
`status = 'queued'`, and the entry moves to `running` before any stage opens. A
second dispatch while the first is in flight finds nothing eligible.

## Decision 6 — no reaper

A process killed mid-run leaves an open `runs` row with a null outcome. This
capability does **not** reconcile it.

A reaper has to guess what happened to a run it did not observe, and the guess
becomes data in the table the eight-week curve is computed over. An open row is
honest and visible — `close_run` already refuses to close an already-closed run,
so a later owner can reap deliberately. Named in tasks as a gap for
`operations`, which owns the machine and is the layer that knows a process died.
