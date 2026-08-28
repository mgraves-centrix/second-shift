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
journal append (day 3), and any night behavior.

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

- `privacy-airlock`: what a capture surface was *offered* is recorded, not only
  what it chose — so a choice forced by an unavailable option is distinguishable
  from a free one.

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
  behavior within days.
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

## Resolved Decisions

Settled via `/openspec:clarify` on 2026-08-27.

**Pending entries.** The capture surface shows a persistent read-only count of
entries waiting to sync — "2 waiting to sync" — and nothing per-item.

The count is enough that a re-tap is obviously unnecessary, which closes the
duplicate hole. It deliberately offers no per-item surface, so there is nothing
for a retry, edit or delete control to attach to later. That is the scope
guarantee, not an oversight: `NOT_BUILDING.md` excludes task management, and a
visible list of items is one product decision away from swipe-to-delete.

Adding any per-item action requires an explicit override naming the line being
crossed, per constitution principle 6.

**The capability offer is recorded.** `entries` carries the report the capture
surface was shown — which policies were offered, which were unavailable, and the
specific probe finding for each unavailable one.

This makes "did I choose `cloud-assisted` deliberately, or because `local-only`
was grayed out that week?" answerable permanently. Without it the local-versus-
cloud token chart can report a degraded endpoint as though it were user
preference, and that chart is how the Airlock is proven rather than asserted.

Stored as JSON on the entry rather than as a normalized table: it is written
once, read rarely, never queried across rows, and its shape follows the
capability report rather than a schema of its own. It lands in migration 0002
and cannot be backfilled for any row captured before it.

**Client timestamps are accepted unbounded, with server receipt recorded
alongside.** `created_at_ms` is the client's instant and is authoritative;
`received_at_ms` records when the server saw it.

Nothing is rejected and nothing is silently corrected. A queue drained three
days later keeps its true capture time, which is the entire point of the offline
requirement. A phone with a wrong clock produces a visible disagreement between
the two columns rather than an invisible corruption of one, so it stays
diagnosable and correctable later.

Rejecting an implausible timestamp would mean losing a real capture on the one
interaction that must never fail. Clamping would overwrite what the client
observed, and a recorded value in this system is what actually happened.
