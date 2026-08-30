-- Link an event to the model call that produced it.
--
-- The night view's hover surfaces the model, tokens, latency and cost behind a
-- moment. Without this column the only routes are parsing `payload_json`, which
-- the telemetry spec forbids and which does not carry those fields anyway, or
-- correlating on (agent_invocation_id, ts_ms) — which is not unique. A single
-- generated night already carries sixteen timestamps holding more than one
-- event, so correlation names the wrong call without any indication that it
-- has. A timeline usually right about cost is worse than one that does not
-- claim to know, because nobody can tell which readings to distrust.
--
-- The first migration to run against a database holding real captured ideas.
-- Nullable by necessity: most events are not produced by a model call, and rows
-- written before this column existed cannot be linked retroactively.
ALTER TABLE events ADD COLUMN model_call_id TEXT REFERENCES model_calls(id);

-- Lookup is always event -> call, one row at a time, on hover.
CREATE INDEX idx_events_model_call ON events(model_call_id);
