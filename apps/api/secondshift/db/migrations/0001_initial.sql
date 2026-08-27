-- Second Shift — core schema.
-- SQLite. Append-only by convention: rows are inserted, superseded, and
-- aggregated in views. Mutation is confined to explicitly nullable
-- completion columns (ended_at_ms, answer, resolution).
--
-- Time is stored as INTEGER epoch milliseconds, UTC. Human-local framing is
-- carried separately on `entries` (captured_tz, tz_offset_min) because the
-- night view renders in the timezone the idea was captured in, not the
-- server's. Never store local time in a timestamp column.

-- Connection pragmas (journal_mode, foreign_keys, busy_timeout) are set by the
-- connection factory, not here: they are properties of a connection, and a
-- PRAGMA cannot run inside the transaction that wraps a migration.

-- ---------------------------------------------------------------------------
-- Capture
-- ---------------------------------------------------------------------------

CREATE TABLE entries (
  id                 TEXT PRIMARY KEY,          -- ULID
  created_at_ms      INTEGER NOT NULL,
  captured_tz        TEXT    NOT NULL,          -- IANA, e.g. America/Los_Angeles
  tz_offset_min      INTEGER NOT NULL,          -- offset at the capture instant
  lat                REAL,                      -- optional; celestial layer only
  lon                REAL,
  modality           TEXT    NOT NULL CHECK (modality IN ('voice','text')),
  raw_text           TEXT,                      -- typed text, or the ASR transcript
  transcript_path    TEXT,
  audio_path         TEXT,
  asr_provider       TEXT,
  asr_confidence     REAL,
  default_policy     TEXT    NOT NULL CHECK (default_policy IN ('local-only','cloud-assisted')),
  status             TEXT    NOT NULL CHECK (status IN ('captured','queued','running','answered','archived')),
  title              TEXT,
  source_device      TEXT,
  capture_profile    TEXT    NOT NULL,          -- compute profile at capture time
  is_synthetic       INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX idx_entries_created ON entries(created_at_ms);
CREATE INDEX idx_entries_status  ON entries(status, created_at_ms);

-- ---------------------------------------------------------------------------
-- The night
-- ---------------------------------------------------------------------------

CREATE TABLE runs (
  id                 TEXT PRIMARY KEY,
  entry_id           TEXT NOT NULL REFERENCES entries(id),
  night_of           TEXT NOT NULL,             -- 'YYYY-MM-DD', local date the night belongs to
  started_at_ms      INTEGER NOT NULL,
  ended_at_ms        INTEGER,
  -- Entry policy is the DEFAULT. This is what the run actually ran under.
  effective_policy   TEXT NOT NULL CHECK (effective_policy IN ('local-only','cloud-assisted')),
  policy_source      TEXT NOT NULL CHECK (policy_source IN ('entry-default','decision-upgrade','profile-forced')),
  compute_profile    TEXT NOT NULL CHECK (compute_profile IN ('spark','workstation','cloud')),
  outcome            TEXT CHECK (outcome IN ('complete','degraded','failed','aborted')),
  furthest_stage     TEXT,
  brain_sha          TEXT,                      -- brain repo HEAD at run start
  code_sha           TEXT,
  is_synthetic       INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX idx_runs_night ON runs(night_of, started_at_ms);
CREATE INDEX idx_runs_entry ON runs(entry_id);

-- Explicit stage table, not a JSON checkpoint blob. "No empty mornings" is a
-- query: the morning brief renders whatever stages reached 'complete'.
CREATE TABLE run_stages (
  id                 TEXT PRIMARY KEY,
  run_id             TEXT NOT NULL REFERENCES runs(id),
  stage              TEXT NOT NULL CHECK (stage IN ('brief','research','mockups','build','critique','distill')),
  seq                INTEGER NOT NULL,
  status             TEXT NOT NULL CHECK (status IN ('pending','running','complete','failed','skipped')),
  started_at_ms      INTEGER,
  ended_at_ms        INTEGER,
  committed_at_ms    INTEGER,                   -- when this stage's output was git-committed
  commit_sha         TEXT,
  UNIQUE(run_id, stage)
);

-- ---------------------------------------------------------------------------
-- Agents and telemetry — instrumented from run one, never retrofitted
-- ---------------------------------------------------------------------------

CREATE TABLE agents (
  id                  TEXT PRIMARY KEY,
  name                TEXT NOT NULL,
  role                TEXT NOT NULL CHECK (role IN ('interviewer','researcher','architect','builder','critic','distiller')),
  version             INTEGER NOT NULL,         -- a prompt change is a new version
  prompt_path         TEXT NOT NULL,
  prompt_sha          TEXT NOT NULL,
  default_model_local TEXT,
  default_model_cloud TEXT,
  created_at_ms       INTEGER NOT NULL,
  retired_at_ms       INTEGER,
  UNIQUE(name, version)
);

CREATE TABLE agent_invocations (
  id                   TEXT PRIMARY KEY,
  run_id               TEXT REFERENCES runs(id),
  agent_id             TEXT NOT NULL REFERENCES agents(id),
  parent_invocation_id TEXT REFERENCES agent_invocations(id),  -- agents call agents
  depth                INTEGER NOT NULL DEFAULT 0,
  stage                TEXT,
  started_at_ms        INTEGER NOT NULL,
  ended_at_ms          INTEGER,
  input_summary        TEXT,
  outcome              TEXT CHECK (outcome IN ('success','degraded','failed')),
  retry_count          INTEGER NOT NULL DEFAULT 0,
  is_synthetic         INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX idx_inv_run    ON agent_invocations(run_id, started_at_ms);
CREATE INDEX idx_inv_parent ON agent_invocations(parent_invocation_id);

CREATE TABLE model_calls (
  id                     TEXT PRIMARY KEY,
  agent_invocation_id    TEXT REFERENCES agent_invocations(id),
  run_id                 TEXT REFERENCES runs(id),
  ts_ms                  INTEGER NOT NULL,
  provider               TEXT NOT NULL CHECK (provider IN ('token-factory','local-vllm','nebius-job','other')),
  compute_profile        TEXT NOT NULL,
  model                  TEXT NOT NULL,
  model_version          TEXT,
  effort                 TEXT,
  prompt_tokens          INTEGER NOT NULL DEFAULT 0,
  completion_tokens      INTEGER NOT NULL DEFAULT 0,
  reasoning_tokens       INTEGER NOT NULL DEFAULT 0,
  total_tokens           INTEGER NOT NULL DEFAULT 0,
  latency_ms             INTEGER,
  time_to_first_token_ms INTEGER,
  estimated_cost_usd     REAL    NOT NULL DEFAULT 0,
  cache_hit              INTEGER NOT NULL DEFAULT 0,
  policy                 TEXT    NOT NULL CHECK (policy IN ('local-only','cloud-assisted')),
  redaction_applied      INTEGER NOT NULL DEFAULT 0,
  is_synthetic           INTEGER NOT NULL DEFAULT 0,

  -- THE PRIVACY AIRLOCK, ENFORCED BY THE DATABASE.
  -- A local-only idea cannot have a row that touched a remote provider.
  -- This is a constraint, not a convention: violating it aborts the write.
  CHECK (NOT (policy = 'local-only' AND provider IN ('token-factory','nebius-job')))
);
CREATE INDEX idx_mc_run      ON model_calls(run_id, ts_ms);
CREATE INDEX idx_mc_provider ON model_calls(provider, ts_ms);

CREATE TABLE tool_calls (
  id                  TEXT PRIMARY KEY,
  agent_invocation_id TEXT REFERENCES agent_invocations(id),
  run_id              TEXT REFERENCES runs(id),
  ts_ms               INTEGER NOT NULL,
  tool                TEXT NOT NULL,            -- 'tavily'
  endpoint            TEXT NOT NULL CHECK (endpoint IN ('search','extract','crawl','research')),
  query_redacted      TEXT,                     -- redacted per policy; raw query is never stored
  policy              TEXT NOT NULL CHECK (policy IN ('local-only','cloud-assisted')),
  credits             REAL    NOT NULL DEFAULT 0,
  result_count        INTEGER,
  latency_ms          INTEGER,
  cached              INTEGER NOT NULL DEFAULT 0,
  outcome             TEXT CHECK (outcome IN ('success','error','quota')),
  is_synthetic        INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX idx_tc_run ON tool_calls(run_id, ts_ms);

-- ---------------------------------------------------------------------------
-- The night feed — shaped for dense time-series playback
-- ---------------------------------------------------------------------------

-- The scrubber renders thousands of rows at 20x. It must never JSON.parse to
-- draw a frame: `lane`, `kind`, `label`, `severity` and `duration_ms` are
-- pre-denormalized for rendering, and `payload_json` is fetched only on hover.
-- Integer PK (not ULID) so playback can cursor by a dense monotonic key.
CREATE TABLE events (
  id                  INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id              TEXT REFERENCES runs(id),
  agent_invocation_id TEXT REFERENCES agent_invocations(id),
  ts_ms               INTEGER NOT NULL,
  lane                TEXT NOT NULL,            -- render lane: agent role, or 'system'
  kind                TEXT NOT NULL CHECK (kind IN (
                        'search','extract','job_dispatch','job_complete','file_write',
                        'model_call','stage_start','stage_end','decision','error','note')),
  label               TEXT NOT NULL,            -- short, pre-rendered
  severity            TEXT NOT NULL DEFAULT 'info' CHECK (severity IN ('debug','info','warn','error')),
  duration_ms         INTEGER,                  -- non-null renders as a bar, null as a tick
  payload_json        TEXT,
  is_synthetic        INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX idx_events_run_ts ON events(run_id, ts_ms);
CREATE INDEX idx_events_ts     ON events(ts_ms);
CREATE INDEX idx_events_lane   ON events(ts_ms, lane);

-- ---------------------------------------------------------------------------
-- Output
-- ---------------------------------------------------------------------------

CREATE TABLE artifacts (
  id                       TEXT PRIMARY KEY,
  run_id                   TEXT NOT NULL REFERENCES runs(id),
  entry_id                 TEXT NOT NULL REFERENCES entries(id),
  stage                    TEXT NOT NULL,
  kind                     TEXT NOT NULL CHECK (kind IN ('brief','research_digest','mockup','build','critique','summary')),
  variant_group            TEXT,                -- shared by parallel variants of one thing
  variant_index            INTEGER,
  variant_rank             INTEGER,             -- critic's ranking within the group
  path                     TEXT NOT NULL,
  content_sha              TEXT,
  bytes                    INTEGER,
  created_at_ms            INTEGER NOT NULL,
  produced_by_invocation_id TEXT REFERENCES agent_invocations(id),
  is_synthetic             INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX idx_artifacts_run     ON artifacts(run_id);
CREATE INDEX idx_artifacts_variant ON artifacts(variant_group, variant_rank);

-- ---------------------------------------------------------------------------
-- The interview — this is the product
-- ---------------------------------------------------------------------------

-- Raised at night when an agent gets stuck; answered in the morning.
-- `consumed_by_run_id` closes the loop and makes the memory claim provable:
-- an answer given Tuesday morning demonstrably changed Tuesday night's run.
CREATE TABLE decisions (
  id                 TEXT PRIMARY KEY,
  entry_id           TEXT NOT NULL REFERENCES entries(id),
  raised_by_run_id   TEXT REFERENCES runs(id),
  raised_by_invocation_id TEXT REFERENCES agent_invocations(id),  -- which interviewer version asked
  raised_at_ms       INTEGER NOT NULL,
  question           TEXT NOT NULL,
  rationale          TEXT,                      -- why the agent could not proceed
  blocking_stage     TEXT,
  answered_at_ms     INTEGER,
  answer             TEXT,
  answer_modality    TEXT CHECK (answer_modality IN ('voice','text')),
  status             TEXT NOT NULL CHECK (status IN ('open','decided','deferred','queued-for-tonight','obsolete')),
  consumed_by_run_id TEXT REFERENCES runs(id),
  is_synthetic       INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX idx_decisions_status ON decisions(status, raised_at_ms);
CREATE INDEX idx_decisions_entry  ON decisions(entry_id);

CREATE TABLE outcomes (
  id           TEXT PRIMARY KEY,
  entry_id     TEXT NOT NULL REFERENCES entries(id),
  artifact_id  TEXT REFERENCES artifacts(id),
  ts_ms        INTEGER NOT NULL,
  label        TEXT CHECK (label IN ('keep','kill','revise')),      -- explicit judgement
  signal       TEXT CHECK (signal IN ('opened','iterated','used','exported','ignored')), -- implicit
  note         TEXT,
  is_synthetic INTEGER NOT NULL DEFAULT 0,
  CHECK (label IS NOT NULL OR signal IS NOT NULL)
);
CREATE INDEX idx_outcomes_entry ON outcomes(entry_id, ts_ms);

-- ---------------------------------------------------------------------------
-- Failure ledger — typed and queryable, consulted at planning time
-- ---------------------------------------------------------------------------

CREATE TABLE failures (
  id                  TEXT PRIMARY KEY,
  run_id              TEXT REFERENCES runs(id),
  agent_invocation_id TEXT REFERENCES agent_invocations(id),
  ts_ms               INTEGER NOT NULL,
  type                TEXT NOT NULL CHECK (type IN (
                        'dependency_build','model_timeout','oom','tool_quota',
                        'tool_error','bad_output','orchestrator_crash','network')),
  signature           TEXT NOT NULL,            -- normalized dedup key
  message             TEXT NOT NULL,
  context_json        TEXT,
  resolution          TEXT,
  resolved_at_ms      INTEGER,
  is_synthetic        INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX idx_failures_sig  ON failures(signature);
CREATE INDEX idx_failures_type ON failures(type, ts_ms);

-- recurrence_count is derived, never stored — the table stays append-only.
CREATE VIEW failure_ledger AS
SELECT
  f.type,
  f.signature,
  COUNT(*)      AS recurrence_count,
  MIN(f.ts_ms)  AS first_seen_ms,
  MAX(f.ts_ms)  AS last_seen_ms,
  (SELECT f2.resolution FROM failures f2
    WHERE f2.signature = f.signature AND f2.resolution IS NOT NULL
    ORDER BY f2.ts_ms DESC LIMIT 1) AS latest_resolution
FROM failures f
WHERE f.is_synthetic = 0
GROUP BY f.type, f.signature;

-- ---------------------------------------------------------------------------
-- Evals — the measurement spine for "it gets better at being me"
-- ---------------------------------------------------------------------------

CREATE TABLE eval_prompts (
  id            TEXT PRIMARY KEY,
  slug          TEXT NOT NULL UNIQUE,
  prompt        TEXT NOT NULL,
  rubric_path   TEXT NOT NULL,
  rubric_sha    TEXT NOT NULL,
  created_at_ms INTEGER NOT NULL,
  active        INTEGER NOT NULL DEFAULT 1
);

-- The judge model and rubric are pinned per run. Without this, an improving
-- score curve is indistinguishable from judge drift.
CREATE TABLE eval_runs (
  id                 TEXT PRIMARY KEY,
  week_of            TEXT NOT NULL,             -- 'YYYY-MM-DD', Monday
  started_at_ms      INTEGER NOT NULL,
  ended_at_ms        INTEGER,
  brain_sha          TEXT NOT NULL,
  code_sha           TEXT NOT NULL,
  judge_model        TEXT NOT NULL,
  judge_model_version TEXT,
  judge_provider     TEXT NOT NULL,
  rubric_sha         TEXT NOT NULL
);

CREATE TABLE eval_results (
  id             TEXT PRIMARY KEY,
  eval_run_id    TEXT NOT NULL REFERENCES eval_runs(id),
  eval_prompt_id TEXT NOT NULL REFERENCES eval_prompts(id),
  sample_index   INTEGER NOT NULL,              -- repeated samples give variance, not a point
  score          REAL NOT NULL,
  subscores_json TEXT,
  output_path    TEXT,
  model_call_id  TEXT REFERENCES model_calls(id),
  UNIQUE(eval_run_id, eval_prompt_id, sample_index)
);

-- ---------------------------------------------------------------------------
-- Payload capture — preserves the option to train later
-- ---------------------------------------------------------------------------

-- model_calls records what a call COST. This records what it SAID. Without it,
-- no night that has already run can ever become training data, because a token
-- count cannot be reconstructed into a prompt. Cheap now, impossible to backfill
-- — the same argument that puts telemetry on day one.
--
-- Text lives on disk, not in SQLite: contexts run to 1M tokens and payloads will
-- outweigh every other table combined within weeks.
--
-- PRIVACY: this table holds raw, unredacted content for local-only ideas. It is
-- local by construction and is excluded from "export your brain" by default. It
-- must never be synced, uploaded, or included in a judge deployment.
CREATE TABLE model_call_payloads (
  model_call_id    TEXT PRIMARY KEY REFERENCES model_calls(id),
  prompt_path      TEXT NOT NULL,      -- data/payloads/<yyyy-mm>/<id>.prompt.json
  completion_path  TEXT NOT NULL,
  prompt_bytes     INTEGER,
  completion_bytes INTEGER,
  captured_at_ms   INTEGER NOT NULL,
  redacted         INTEGER NOT NULL DEFAULT 0,
  -- synthetic data and anything the user excludes never enters a training set
  training_eligible INTEGER NOT NULL DEFAULT 1,
  retention_class  TEXT NOT NULL DEFAULT 'standard'
                   CHECK (retention_class IN ('standard','ephemeral','pinned'))
);
CREATE INDEX idx_payloads_eligible ON model_call_payloads(training_eligible, captured_at_ms);

-- The interviewer preference dataset, materialized from data already collected.
-- `accepted` is the label: a question worth asking got decided; one that was
-- deferred or went obsolete was not. This is the cleanest training signal in the
-- system, and it accumulates from the first week of dogfooding whether or not a
-- fine-tune is ever run.
CREATE VIEW interviewer_training_pairs AS
SELECT
  d.id            AS decision_id,
  d.entry_id,
  d.question,
  d.rationale,
  d.answer,
  d.status,
  CASE WHEN d.status = 'decided'                  THEN 1
       WHEN d.status IN ('deferred','obsolete')   THEN 0
       ELSE NULL END AS accepted,
  d.raised_at_ms,
  d.answered_at_ms,
  ag.name    AS agent_name,
  ag.version AS agent_version,
  r.brain_sha
FROM decisions d
LEFT JOIN agent_invocations ai ON ai.id = d.raised_by_invocation_id
LEFT JOIN agents ag            ON ag.id = ai.agent_id
LEFT JOIN runs r               ON r.id  = d.raised_by_run_id
WHERE d.is_synthetic = 0;

-- ---------------------------------------------------------------------------
-- Rollups — what the dashboard reads
-- ---------------------------------------------------------------------------

CREATE VIEW run_cost AS
SELECT
  r.id AS run_id, r.entry_id, r.night_of, r.effective_policy, r.compute_profile,
  COALESCE(SUM(CASE WHEN mc.provider = 'local-vllm'    THEN mc.total_tokens END), 0) AS local_tokens,
  COALESCE(SUM(CASE WHEN mc.provider IN ('token-factory','nebius-job') THEN mc.total_tokens END), 0) AS cloud_tokens,
  COALESCE(SUM(mc.estimated_cost_usd), 0) AS model_cost_usd,
  COALESCE((SELECT SUM(tc.credits) FROM tool_calls tc WHERE tc.run_id = r.id), 0) AS tool_credits
FROM runs r
LEFT JOIN model_calls mc ON mc.run_id = r.id
WHERE r.is_synthetic = 0
GROUP BY r.id;

-- The Privacy Airlock as a chart: local-only nights show cloud_tokens = 0.
CREATE VIEW night_totals AS
SELECT night_of,
       SUM(local_tokens) AS local_tokens,
       SUM(cloud_tokens) AS cloud_tokens,
       SUM(model_cost_usd) AS model_cost_usd,
       SUM(tool_credits) AS tool_credits,
       COUNT(*) AS runs
FROM run_cost GROUP BY night_of;

-- The learning claim, proven economically.
CREATE VIEW cost_per_accepted_artifact AS
SELECT r.night_of,
       SUM(rc.model_cost_usd) AS spend_usd,
       COUNT(DISTINCT CASE WHEN o.label = 'keep' THEN a.id END) AS accepted,
       CASE WHEN COUNT(DISTINCT CASE WHEN o.label = 'keep' THEN a.id END) = 0 THEN NULL
            ELSE SUM(rc.model_cost_usd) / COUNT(DISTINCT CASE WHEN o.label = 'keep' THEN a.id END)
       END AS usd_per_accepted
FROM runs r
JOIN run_cost rc ON rc.run_id = r.id
LEFT JOIN artifacts a ON a.run_id = r.id AND a.is_synthetic = 0
LEFT JOIN outcomes  o ON o.artifact_id = a.id
WHERE r.is_synthetic = 0
GROUP BY r.night_of;
