-- The eval tables are the measurement spine and were the only accumulating
-- tables with no `is_synthetic` column.
--
-- Ten tables carry the flag and the rollup views exclude it. These three did
-- not, and the runner never filtered on one, so an evaluation run executed on a
-- judge deployment wrote unmarked rows straight into the curve the submission
-- is built on. Nothing prevented it and nothing would have shown it afterwards:
-- a synthetic score is a number like any other once it is in the table.
--
-- Principle 5's violation clause names "synthetic rows without
-- `is_synthetic = 1`". This is that, on the one set of rows where it is least
-- recoverable — the whole claim is a week-1 to week-8 comparison, and a curve
-- with a demo instance's scores in it cannot be cleaned afterwards without
-- knowing which rows came from where.
--
-- `DEFAULT 0` because every row that exists today was written on the personal
-- instance. Backfilling anything else would be inventing provenance.

ALTER TABLE eval_prompts ADD COLUMN is_synthetic INTEGER NOT NULL DEFAULT 0;
ALTER TABLE eval_runs    ADD COLUMN is_synthetic INTEGER NOT NULL DEFAULT 0;
ALTER TABLE eval_results ADD COLUMN is_synthetic INTEGER NOT NULL DEFAULT 0;

-- The curve is read by run. An index on the flag alone would not help; this is
-- the access path `status` and the week-over-week comparison actually take.
CREATE INDEX idx_eval_runs_real ON eval_runs(is_synthetic, started_at_ms);
