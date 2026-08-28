## 1. Migration 0002 — the irreversible part

Blocks everything. This is the last migration that runs against empty tables;
after day-3 dogfooding it would alter the only copy of a week of captured ideas.

- [ ] 1.1 Write `db/migrations/0002_capture.sql` adding `events.entry_id` as a nullable foreign key to `entries`, with an index on `(entry_id, ts_ms)` so an entry's history is retrievable without scanning.
- [ ] 1.2 Add the capability-offer column to `entries` if the clarification resolved in favour of recording what the capture surface was offered.
- [ ] 1.3 Test: migration applies to a fresh database and to one already at version 1, and `PRAGMA integrity_check` returns ok in both cases.
- [ ] 1.4 Test: an event naming an entry survives a round trip and is retrievable by entry.

## 2. Repository and recorder corrections

Depends on group 1. These are defects in shipped code, fixed before they matter.

- [ ] 2.1 `queued_entries` excludes synthetic rows and entries with no content, and is renamed to state that it returns dispatch-eligible entries rather than merely queued ones.
- [ ] 2.2 Add `ineligible_entries` returning queued entries that cannot be dispatched, each with the reason — so an entry is never silently invisible.
- [ ] 2.3 Add `get_entry`, so the idempotent replay path can return what the server already holds.
- [ ] 2.4 `insert_entry` requires an explicit capture instant rather than defaulting to insert time, and validates that the supplied identifier is a well-formed ULID whose embedded timestamp matches.
- [ ] 2.5 Add a named entry status transition operation that refuses a transition not permitted from the current status. No generic entry update.
- [ ] 2.6 Add a recorder-owned entry write that takes the recorder's lock, and document `insert_entry` as the unlocked primitive that request handlers must not call.
- [ ] 2.7 Extend the event recorder to accept an entry, and add an entry-history read.
- [ ] 2.8 Test: a synthetic queued entry is absent from the eligible set and present in the ineligible set with its reason.
- [ ] 2.9 Test: an empty text entry is ineligible with its reason, not absent.
- [ ] 2.10 Test: `insert_entry` rejects a malformed identifier, and rejects one whose embedded timestamp disagrees with the capture instant.
- [ ] 2.11 Test: a status transition that is not permitted from the current status is refused.
- [ ] 2.12 Test: concurrent writes from multiple threads through the recorder serialize and lose nothing.

## 3. Capture API

Depends on group 2.

- [ ] 3.1 Add FastAPI, uvicorn and pydantic to `pyproject.toml`, regenerate `constraints.txt` from a clean install, and verify the pins resolve from scratch.
- [ ] 3.2 Request and response models: identifier, capture instant, IANA zone, UTC offset, policy, text, optional location and capture profile. Reject anything asserting synthetic status.
- [ ] 3.3 `POST /entries` writing through the recorder-owned path, returning the stored entry on replay without creating a second row or recording a failure.
- [ ] 3.4 Record a capture event against the entry, including one for a replay whose content diverges from what is stored.
- [ ] 3.5 `GET /capabilities` serving the capability report, with unavailable policies present and marked with their finding.
- [ ] 3.6 Derive a title from content deterministically, with no model call.
- [ ] 3.7 Read home coordinates from `config/location.toml`, allowing a per-request override.
- [ ] 3.8 Test: an entry captured at one instant and submitted much later stores the capture instant, not the receipt instant.
- [ ] 3.9 Test: submitting the same entry twice yields one row, two successes, and no failure row.
- [ ] 3.10 Test: a replayed identifier with altered text keeps the stored version and records the divergence as an event on that entry.
- [ ] 3.11 Test: `local-only` is accepted and stored intact on a profile that cannot honor it, and the entry is then quarantined rather than rewritten.
- [ ] 3.12 Test: `GET /capabilities` on a degraded profile returns `local-only` marked unavailable with the specific probe finding, not a generic message.
- [ ] 3.13 Test: a request asserting synthetic status is ignored and the server's determination is recorded.

## 4. PWA

Depends on group 3. Installability is polish; the logged entry is the gate.

- [ ] 4.1 Next.js app under `apps/web` with the capture screen: text field, policy selector, submit.
- [ ] 4.2 Render policies from `GET /capabilities`, showing unavailable ones disabled with their reason rather than hiding them.
- [ ] 4.3 Generate the identifier and capture instant client-side, and write to IndexedDB before any network attempt.
- [ ] 4.4 Drain the queue on reconnect, replaying complete records unchanged.
- [ ] 4.5 Capture the device IANA zone and its offset at the moment of capture.
- [ ] 4.6 Implement the pending-entry treatment the clarification settled, read-only.
- [ ] 4.7 Manifest and service worker for installability.
- [ ] 4.8 Test: capture with the network disabled queues locally and reports success.
- [ ] 4.9 Test: restoring connectivity drains the queue and the stored capture instant is the original one.
- [ ] 4.10 Test: an unavailable policy renders disabled with its reason and cannot be submitted.

## 5. Day 2 pass gates

- [ ] 5.1 Gate: an entry captured from a phone browser lands in SQLite with the correct timezone and offset.
- [ ] 5.2 Gate: airplane-mode capture queues locally and syncs on reconnect, preserving the capture instant.
- [ ] 5.3 Gate: the full suite passes on the Spark under Python 3.12 on aarch64, transferred with AppleDouble sidecars suppressed.
- [ ] 5.4 Gate: `openspec validate --strict` passes for the change and for all canonical specs.
- [ ] 5.5 Update `docs/WEEK_ONE.md` and `docs/SPEC_ROADMAP.md` with what shipped and what day 3 inherits.
