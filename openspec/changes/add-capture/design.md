## Context

The foundations are built and archived: schema, telemetry, providers, profile
resolution, airlock. Capture is the first change that writes rows a human cares
about, and the last change before real data exists.

That timing dominates every decision here. `docs/WEEK_ONE.md` puts dogfooding on
day 3, one day after this. Migration 0002 can add a column to an empty table;
migration 0003 would add one to a table holding the only copy of a week of
captured ideas.

## Goals / Non-Goals

**Goals:**
- Text capture from a phone to a durable row, offline-tolerant, timezone-correct.
- Define eligibility — what makes an entry visible to the night — because
  nothing currently does beyond a status string.
- Land the schema changes that become unrecoverable after day 3.
- Fix the defects the pre-review found in shipped code.

**Non-Goals:**
- Voice, ASR, microphone, HTTPS. Day 3–4.
- The brain journal append. Day 3, though the seam is reserved here.
- Any night behaviour, retrieval, or the interview.
- A queue management UI. See the scope boundary below.

## Decisions

### Entry writes go through the recorder's lock

ADR 0008 established that `check_same_thread` is off and serialization is the
`Recorder`'s lock. `Repository.insert_entry` predates that and takes no lock,
because on day 1 nothing else wrote concurrently.

FastAPI runs synchronous handlers in a threadpool. A capture arriving while the
night orchestrator writes is a genuine interleaving on a connection whose own
thread guard is deliberately disabled.

`Recorder` gains an entry write that takes the lock, and the capture handler
uses it. `Repository.insert_entry` stays as the unlocked primitive for tests and
migrations, with a docstring saying so — the alternative, putting a lock inside
the repository, would give two independent locks over one connection, which is
worse than none.

*Alternative rejected:* making the endpoint `async` so it runs on the event loop
and cannot interleave. That is true only until the first `await` in the handler,
and it makes the safety property depend on nobody adding one later.

### Eligibility is a defined query, not a status string

Today "eligible for a run" means `status = 'queued'`, expressed only inside
`Repository.queued_entries`. That already has a hole: it does not filter
`is_synthetic`, so the day-6 night generator will feed synthetic entries to the
real orchestrator.

Eligibility becomes explicit: `status = 'queued'`, `is_synthetic = 0`, and a
non-empty body. The last is not currently enforceable — an entry with
`modality = 'text'` and `raw_text = NULL` passes every constraint, screens as
dispatchable, and gets a run with nothing to reason about.

*Enforced where?* At the repository query rather than as a CHECK constraint. A
CHECK would be stronger, but `raw_text` is legitimately null for a voice entry
whose transcript has not arrived, so the constraint would have to encode a rule
about modality that will change when voice lands.

### `created_at_ms` is the client's instant, and the ULID must agree

The client generates the ULID, which embeds its own millisecond timestamp.
`created_at_ms` must equal it. If the server overwrites either, then
`ORDER BY created_at_ms, id` — the ordering used for the queue — sorts by two
disagreeing clocks and is not a total order over anything meaningful.

This is why replay must not re-mint an id, and why `insert_entry`'s convenience
default of `now_ms()` is wrong for this path specifically.

### Offline queue: the client owns identity

The PWA writes to IndexedDB before any network call, with the ULID and timestamp
generated at that moment. Draining is a replay of complete records, not a
deferred construction — nothing about the entry is decided at drain time.

This is what makes idempotency work: the server can treat a replay as a lookup
because the client's record is already complete and immutable.

### The scope boundary around a pending-entry view

`NOT_BUILDING.md` excludes task management, and a list of pending items with
retry and delete is task management wearing a different name. But showing
nothing is a real failure: the user re-taps, the idempotency key silently
absorbs it, and they believe they captured two ideas.

This is the change's sharpest open question rather than a decision, and it is
marked as one. Whatever the answer, the constraint is that a pending view is
**read-only status**. The moment it grows an action other than "capture another",
it has crossed the line and needs an explicit override.

## Risks / Trade-offs

**This is the last cheap migration.** Everything in 0002 that turns out to be
missing becomes a data migration over irreplaceable rows. The pre-review found
two such omissions; there may be a third nobody has thought of. Mitigation: the
review was adversarial and specifically hunted for unrecoverable omissions, and
the second open question exists because the answer changes 0002's content.

**First runtime dependencies.** FastAPI, uvicorn, pydantic, and Next.js. Until
now the package had none outside the standard library, which is why the day-1
foundation survived every spike risk. These install cleanly on aarch64 — none
carries a compiled extension that has caused trouble — but the property of
having no runtime dependencies is being spent, and it should be spent knowingly.

**Client clock skew is unbounded.** A phone with a wrong clock writes a wrong
`created_at_ms` and there is no server-side correction. The third open question
covers what, if anything, bounds it.

**The PWA is unproven ground.** Installability, IndexedDB persistence and
service-worker drain are each individually simple and collectively fiddly. The
abort path is a plain responsive page: the logged entry is the gate, and
installability is polish.
