## Why

Day 2. Capture is the critical path to day-3 dogfooding, and dogfooding starts a
clock that cannot be restarted — the week-1-versus-week-8 brain diff is the
submission's centerpiece and there is no way to backfill a week of captures.

Everything downstream waits on this: the brain has nothing to commit, the night
has nothing to run on, and the eval baseline has no brain to pin a SHA against.

An adversarial review of the existing specs and code before writing this
proposal found four defects and two unrecoverable omissions. Three of them are
in code already archived as complete, and two require a migration **before real
rows exist** — after day 3, the fix is no longer a migration but a data-loss
event. That is why this change is larger than "add an endpoint".

## What Changes

**Capture path.** `POST /entries` accepting a client-generated ULID, the
client's capture instant, its IANA zone and UTC offset, the chosen policy and
the text. `GET /capabilities` serving the policy availability report. A minimal
installable PWA that captures text, queues offline, and drains on reconnect.

**Migration 0002 — the part that cannot wait.**

- `events.entry_id`. Capture-time events currently have nowhere to attach:
  `events` carries `run_id` and `agent_invocation_id`, and capture has neither.
  Every capture-time event would be written with `run_id = NULL` and be
  unreadable through `Repository.timeline`, which filters on `run_id`. The
  existing `Transcriber` already emits one such orphan.
- `entries.offered_capability_json`. See the open question below.

**Defects found in shipped code, fixed here.**

- `Repository.queued_entries()` does not filter `is_synthetic`. Once the day-6
  night generator writes synthetic queued entries, the real orchestrator
  dispatches them. Capture is where "eligible for a run" is defined, so the fix
  belongs here.
- `Repository.insert_entry` writes outside the recorder's lock. ADR 0008
  requires anything writing outside `Recorder` to take that lock, and
  `check_same_thread=False` means the guard that would have caught this is
  deliberately off. FastAPI runs sync handlers in a threadpool, so a capture
  concurrent with a night write is a real interleaving, not a theoretical one.
- `insert_entry` defaults `created_at_ms` to insert time. For a queue drained
  hours later that records the receipt instant, silently, for exactly the
  entries the offline requirement exists to serve.
- No `Repository.get_entry`. The idempotent replay path cannot return what the
  server already holds without it.

Not in this change: voice, ASR, HTTPS/microphone (day 3–4 spike), the brain
journal append (day 3), and any night behaviour.

## Capabilities

### New Capabilities
- `capture`: an idea becoming a durable, timezone-correct, policy-carrying row —
  including offline queueing, idempotent replay, and what makes an entry
  eligible for a run.

### Modified Capabilities
- `persistence`: `queued_entries` must exclude synthetic rows; entry status
  transitions become a named completion operation rather than absent.
- `telemetry`: events may attach to an entry, not only to a run or an
  invocation.

`privacy-airlock` may also gain a requirement — that what a capture surface was
*offered* is recorded, not only what it chose. That depends on the second open
question below, so the delta is written once the question is answered rather
than assumed now.

## Constitution Compliance

| Principle | Status | Note |
|---|---|---|
| 1. Brain plaintext under git | Compliant | Journal append is day 3. This change reserves the seam and does not put a git commit in the request path. |
| 2. Privacy Airlock | **Implements** | Policy is stored as *intent*, never filtered by availability. The capability report is served as a report, not as a list of selectable options. |
| 3. No empty mornings | Compliant | Defines eligibility so an entry cannot be captured into a state nothing ever reads. |
| 4. Text-first | **Implements** | The text path is complete end to end with zero ASR dependency, before the microphone spike exists. |
| 5. One codebase, two deployments | Compliant | `is_synthetic` is server-derived and never accepted from a request body. No demo-only branch in the handler. |
| 6. Scope boundary | **At risk — see marker** | A queued-entry view is where an inbox gets in. Read-only status is in scope; anything editable is not. |
| 7. Telemetry from line one | **Implements** | `events.entry_id` is what makes capture-time telemetry recordable at all. Without it, capture is silently exempt. |

No violations. Principle 6 is flagged rather than clean: the open question below
is precisely the boundary, which is why it is a marker and not a decision.

## Decisions taken without a marker

- **Capture writes `status = 'queued'`**, not `'captured'`. `queued_entries()`
  filters on `'queued'`; an entry captured into any other status is invisible to
  screening, quarantine and the night, permanently. `'captured'` is documented
  as unused rather than left as a trap.
- **`created_at_ms` is client-supplied**, always, and equals the timestamp
  embedded in the client's ULID. Otherwise `ORDER BY created_at_ms, id`
  disagrees with itself.
- **Replay is a silent success**: `200` with the stored entry. Not `409`, and
  not an `IntegrityError` — an unhandled duplicate would classify as
  `orchestrator_crash` and swamp the failure ledger with routine client
  behaviour within days.
- **A replayed id with different content keeps the stored version.** Entries are
  append-only; the divergence is recorded as an event rather than resolved.
- **`capture_profile` is the profile the client was told about**, sent with the
  request, falling back to the server's at insert. Stamping the drain-time
  profile would make the column false for exactly the offline entries it exists
  to describe.
- **Latitude and longitude come from config**, with an optional per-request
  override. Never from a browser geolocation prompt.
- **Titles are derived without a model.** A model-derived title would need an
  `agents` row, an invocation, a policy-carrying model call, and a priced
  model — and would fail every capture until day 5.

## Impact

**New:** `apps/api/secondshift/api/` (routes, schemas), `apps/web/` (PWA),
`config/location.toml`, migration `0002`.

**Changed:** `Repository` — `queued_entries`, `insert_entry`, plus `get_entry`
and a named status transition.

**Dependencies:** FastAPI, uvicorn, pydantic on the API side; Next.js on the
web side. The first runtime dependencies in the project — until now the package
had none beyond the standard library.

**Risk:** this is the last change before real data exists. Migration 0003 is
cheap; migration 0003 *that alters existing rows* is not.

## Open Questions

[NEEDS CLARIFICATION: What does the capture surface show for an entry that is queued offline and not yet acknowledged by the server? Silence invites a re-tap, and the idempotency key then swallows the duplicate invisibly — the user believes they captured two ideas and one vanished. But a queued-entry list with retry, edit or delete is task management, which NOT_BUILDING.md excludes. Where is the line: a transient confirmation only, a read-only pending count, or a read-only list of pending items?]

[NEEDS CLARIFICATION: Should `entries` record the capability report that was shown at capture — which policies were offered, which were unavailable, and why? Without it, "did I choose cloud-assisted deliberately, or because local-only was greyed out that week?" is permanently unanswerable, and the local-versus-cloud chart may tell a story about a degraded endpoint rather than about intent. It costs one column and must land in migration 0002; after day 3 it cannot be backfilled for any existing row.]

[NEEDS CLARIFICATION: What bounds a client-supplied `created_at_ms`? A phone with a fast clock produces a future timestamp; a three-day-old queued entry drains with a past one, which is correct and must be preserved. Options: accept anything and record server receipt time alongside; reject timestamps more than some window in the future; or clamp and record that clamping occurred. Sort order across the whole system depends on this column.]
