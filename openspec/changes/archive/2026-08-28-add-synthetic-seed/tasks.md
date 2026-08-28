## 1. The generator

- [x] 1.1 Create `packages/seed/` with a deterministic generator seeded from an explicit value, using no source of randomness that is not seeded.
- [x] 1.2 Generate entries with plausible capture instants, timezones and policies, content clearly labeled as synthetic rather than imitating real thought.
- [x] 1.3 Generate a run with its stage checkpoints, spanning several hours.
- [x] 1.4 Generate a nested invocation tree at least three deep, with agents in distinct roles.
- [x] 1.5 Generate model calls with plausible token counts, latencies and costs, using local providers under local-only policy so the airlock accepts them.
- [x] 1.6 Generate tool calls with redacted queries and credit counts.
- [x] 1.7 Generate typed failures attached to invocations, drawn from the taxonomy.
- [x] 1.8 Generate artifacts in variant groups with distinct critic rankings.
- [x] 1.9 Generate at least four hundred timeline events across multiple lanes, distributed over the night rather than clustered.
- [x] 1.10 Write everything through the repository layer so generated work obeys the same constraints as real work.

## 2. Verification

- [x] 2.1 Test: a generated night has a run, stages, an invocation tree of depth three or more, and 400+ events across multiple lanes.
- [x] 2.2 Test: the same seed produces identical nights in two separate databases; different seeds differ.
- [x] 2.3 Test: every generated row carries the synthetic flag.
- [x] 2.4 Test: the cost and totals views report nothing from a generated night written alongside real rows.
- [x] 2.5 Test: generated queued entries are absent from the dispatch-eligible set.
- [x] 2.6 Test: a generated run's timeline is renderable, with the scalar columns the view reads.
- [x] 2.7 Test: generated local-only model calls name only local providers and are accepted by the database.
- [x] 2.8 Test: generated failures are typed, attached to invocations, and absent from the failure ledger.
- [x] 2.9 Test: events are distributed across the night rather than clustered at one instant.

## 3. Entry point and gates

- [x] 3.1 Add a command-line entry point taking a seed and a target database.
- [x] 3.2 Gate: full suite passes locally and on the Spark.
- [x] 3.3 Gate: `openspec validate --strict` for the change and every canonical spec.
- [x] 3.4 Gate: both check scripts pass.
