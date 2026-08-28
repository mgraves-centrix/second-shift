-- Capture. The last migration that runs against empty tables: after day-3
-- dogfooding these hold the only copy of a week of captured ideas.

-- Capture-time events have neither a run nor an invocation to attach to. Without
-- this they would be written with run_id NULL and be unreadable through the
-- timeline query, which filters on run_id — making capture a silent exemption
-- from telemetry-from-line-one rather than an instrumented path.
ALTER TABLE events ADD COLUMN entry_id TEXT REFERENCES entries(id);
CREATE INDEX idx_events_entry ON events(entry_id, ts_ms);

-- What the capture surface was OFFERED, not only what it chose. Without it a
-- cloud-assisted choice made because local-only was grayed out is
-- indistinguishable from one made freely, and the local-versus-cloud token
-- ratio can report a degraded endpoint as though it were user preference.
ALTER TABLE entries ADD COLUMN offered_capability_json TEXT;

-- The server's receipt instant, beside the client's authoritative capture
-- instant. Neither is corrected against the other: a device with a wrong clock
-- produces a visible disagreement rather than an invisible corruption, and a
-- queue drained three days later keeps its true capture time.
ALTER TABLE entries ADD COLUMN received_at_ms INTEGER;
