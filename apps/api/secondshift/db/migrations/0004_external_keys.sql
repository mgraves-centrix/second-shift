-- Telemetry collected from out-of-process work, keyed so it is recorded once.
--
-- A job gives each invocation and model call an id when it does the work, not
-- when it reports it, so collecting the same report twice — a retried poll, a
-- restarted job, a second `await_result` — presents the same ids. The key is the
-- dispatching invocation and that id together: two variants whose jobs numbered
-- their work the same way are still two variants.
--
-- Enforced here rather than trusted to the reporter. Duplicated rows inflate the
-- cost curve and the local-versus-cloud comparison, silently, and those are the
-- numbers the Nebius claim is read from.
--
-- Null for everything recorded in process, which is every row that exists
-- today. The unique indexes are partial so those rows never collide.

ALTER TABLE agent_invocations ADD COLUMN external_key TEXT;
ALTER TABLE model_calls       ADD COLUMN external_key TEXT;

CREATE UNIQUE INDEX idx_invocations_external_key
  ON agent_invocations(external_key) WHERE external_key IS NOT NULL;
CREATE UNIQUE INDEX idx_model_calls_external_key
  ON model_calls(external_key) WHERE external_key IS NOT NULL;
