## 1. Loading content

- [ ] 1.1 Load prompts from a file into `eval_prompts`, carrying an active flag, without deleting unselected candidates.
- [ ] 1.2 Load the rubric and record its content hash, so the hash follows the file.
- [ ] 1.3 Seed the ten existing candidates as inactive, so selecting five is marking them active.
- [ ] 1.4 Test: only active prompts are returned for a run; inactive ones remain recorded.
- [ ] 1.5 Test: editing the rubric changes the recorded hash.

## 2. The runner

Depends on group 1.

- [ ] 2.1 Define the judge interface — an output and a rubric in, structured per-dimension scores out — and a stub implementation for tests.
- [ ] 2.2 Run each active prompt the configured number of times, recording each result with its sample index.
- [ ] 2.3 Record the judge model, its version and the rubric hash on the run.
- [ ] 2.4 Record the brain commit at the start of the run.
- [ ] 2.5 Support recording a baseline with no judge available, marked as awaiting scoring.
- [ ] 2.6 Score an awaiting-scoring run later, attributing results to the brain commit recorded at baseline and leaving that commit unchanged.
- [ ] 2.7 Record a typed failure and no score when a judgement cannot be read as structured scores.
- [ ] 2.8 Record successful samples and mark the run incomplete when some fail.
- [ ] 2.9 Summarize a run as a central value and a spread per prompt.

## 3. Verification

- [ ] 3.1 Test: three samples per prompt are recorded with distinct sample indices.
- [ ] 3.2 Test: judge model, version and rubric hash are recorded on the run.
- [ ] 3.3 Test: a baseline recorded without a judge is marked awaiting scoring and records prompts, rubric hash and brain commit.
- [ ] 3.4 Test: scoring days later, after the brain has moved, attributes results to the baseline commit and leaves it unchanged.
- [ ] 3.5 Test: scoring with no judge configured fails clearly rather than recording unscored results as scored.
- [ ] 3.6 Test: an unparseable judgement records a typed failure and no score.
- [ ] 3.7 Test: a partially failed run records its successes and is identifiable as incomplete.
- [ ] 3.8 Test: a summary reports both a central value and a spread.

## 4. Entry point and gates

- [ ] 4.1 Add a command-line entry point to record a baseline, to score an awaiting run, and to summarize.
- [ ] 4.2 Gate: full suite passes locally and on the Spark.
- [ ] 4.3 Gate: `openspec validate --strict` for the change and every canonical spec.
- [ ] 4.4 Gate: both check scripts pass.
