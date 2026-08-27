# Data Model

Schema lives in [`apps/api/secondshift/db/schema.sql`](../apps/api/secondshift/db/schema.sql)
and is the authority. This document explains the choices that are not obvious
from reading the DDL.

## Conventions

- **Time** is `INTEGER` epoch milliseconds, UTC, everywhere. Human-local framing
  is carried separately on `entries` as `captured_tz` (IANA) and
  `tz_offset_min`. The night view renders in the timezone the idea was captured
  in, not the server's. No column ever stores local time.
- **Ids** are ULIDs (`TEXT`), except `events.id`, which is a dense
  autoincrementing integer so playback can cursor by a monotonic key.
- **Append-only.** Rows are inserted and superseded. Mutation is confined to
  nullable completion columns: `ended_at_ms`, `answer`, `resolution`.
  Anything that looks like a counter is a view.

## Decisions worth defending

**`is_synthetic` on every table.** Development data, the synthetic night
generator, and the judge instance's seeded persona all write to the same schema.
Without a flag, they contaminate the eight-week eval trend and the cost curves —
the exact numbers the submission rests on. Every rollup view filters
`is_synthetic = 0`. This costs one column and prevents an unrecoverable class of
error in week seven.

**Policy is two fields, not one.** `entries.default_policy` is the intent set at
capture. `runs.effective_policy` is what the run actually executed under, plus
`policy_source` recording why it differs (`entry-default`, `decision-upgrade`,
`profile-forced`). Without this you cannot answer "was this artifact ever
touched by cloud compute" after an idea is upgraded — and that question is the
whole Airlock.

**The Airlock is a `CHECK` constraint.** `model_calls` refuses any row where
`policy = 'local-only'` and the provider is remote. Verified: the insert aborts
with `CHECK constraint failed`. The privacy guarantee is enforced by the storage
engine, not by remembering to write an `if` statement in every call site.

**`events` is denormalized for rendering.** The scrubber draws thousands of rows
at 20x and must not parse JSON to produce a frame. `lane`, `kind`, `label`,
`severity` and `duration_ms` are pre-rendered scalar columns; `payload_json` is
fetched only on hover. `duration_ms` non-null renders as a bar, null as a tick —
so a 40-second Tavily crawl and an instantaneous file write read differently at
a glance.

**`run_stages` is a table, not a JSON checkpoint blob.** "No empty mornings" then
becomes a query: the morning brief renders every stage that reached `complete`,
regardless of what happened after. Graceful degradation falls out of the schema
instead of being handled in application code.

**`decisions.consumed_by_run_id`.** This closes the loop and makes the memory
claim provable — an answer given Tuesday morning demonstrably changed Tuesday
night's run. Without it, "your answers feed the next run" is an assertion.

**`failures.signature` with `recurrence_count` as a view.** The ledger stays
append-only; recurrence is derived by grouping on a normalized signature. The
planner queries `failure_ledger` before dispatching a stage, which is what makes
the system stop repeating mistakes rather than merely logging them.

**Evals pin the judge.** `eval_runs` records `judge_model`,
`judge_model_version` and `rubric_sha`. If the scoring model drifts, an
improving curve measures the judge, not the brain. `eval_results.sample_index`
exists so each prompt is sampled repeatedly and reported as mean ± spread —
five prompts scored once a week is 45 points of noise with no error bars.

**Vectors are `BLOB`s in SQLite, searched by brute-force cosine in numpy.**
At the projected scale — roughly 600 entries by week eight — exact search over
an in-memory array is instant, and correct rather than approximate. It also
installs identically on aarch64, x86, and in the judge container, which the
portability requirement makes decisive. This sits behind the `Embedder` and
retrieval interfaces; swapping in a real index later is a one-module change.
LanceDB is not adopted. See `docs/decisions/0002`.

**`model_call_payloads` is separate from `model_calls`.** One records what a
call cost, the other what it said. They are split because the cost row is small,
indexed and queried constantly, while payload text is large, written once, and
read rarely. Keeping prompts on disk behind a path reference stops 1M-token
contexts from dominating every query plan in the database. See
`docs/decisions/0007` — the point of capturing payloads at all is to preserve the
option of training later, which cannot be backfilled from token counts.

## Entity map

```
entries ──┬─▶ runs ──┬─▶ run_stages
          │          ├─▶ agent_invocations ──┬─▶ model_calls
          │          │        │              └─▶ tool_calls
          │          │        └─(parent_invocation_id, self-referential tree)
          │          ├─▶ events
          │          ├─▶ artifacts ──▶ outcomes
          │          └─▶ failures
          └─▶ decisions ──(consumed_by_run_id)──▶ runs
```
