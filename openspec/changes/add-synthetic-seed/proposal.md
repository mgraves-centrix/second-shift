## Why

The night scrubber is the signature UI element, and it cannot be built against
four real events. Real nights will not produce dense data until the orchestrator
exists, which is weeks away — so every hour of frontend work is blocked on
something that has not been written.

The generator is also not throwaway. The judge deployment needs a seeded
persona with zero real data, and that seed is this same code. Building it once
serves both, and building it now unblocks the work that most needs a head start.

## What Changes

A generator that writes a complete synthetic night: entries, a run with its
stages, a nested invocation tree, model calls with plausible token counts,
latencies and costs, tool calls, typed failures, artifacts in variant groups
with critic rankings, and several hundred timeline events across lanes.

Every row carries `is_synthetic = 1`. The rollup views already exclude those, so
a generated night is renderable and uncountable at the same time — which is the
property that lets it sit in the same database as real work.

Deterministic from a seed: the same seed produces the same night, byte for byte.
A demo that renders differently each time cannot be rehearsed, and a test that
asserts on generated data needs the data to hold still.

Not in this change: the scrubber itself, or the judge deployment's persona
content. This produces the shape; what a judge reads is a later refinement.

## Capabilities

### New Capabilities
- `synthetic-seed`: generating a complete, structurally faithful night that is
  renderable, reproducible, and permanently excluded from measurement.

## Constitution Compliance

| Principle | Status | Note |
|---|---|---|
| 5. One codebase, two deployments | **Implements** | The judge deployment's seed is this generator. "Synthetic rows without `is_synthetic = 1`" is the principle's named violation, and every row this writes carries it. |
| 7. Telemetry from line one | Compliant | Generated telemetry is structurally identical to real telemetry — same tables, same shapes — because a scrubber built against a different shape would not render real nights. |
| 2. Privacy Airlock | Compliant | Generated `local-only` runs carry only local providers, so the database `CHECK` accepts them. A generator that could not satisfy the airlock would be generating something this system cannot produce. |

No violations.

## Decisions taken without a marker

- **Deterministic from a seed.** The same seed yields the same night. Demos are
  rehearsable and tests can assert on specific rows.
- **Structure is faithful; content is labeled.** Generated ideas read as
  obviously synthetic rather than imitating real captured thoughts. The
  structure is what unblocks the scrubber, and content that pretends to be
  someone's real thinking is worse than content that admits what it is. Judge-
  facing text is a later refinement against this same structure.
- **It writes through the repository layer**, not raw SQL, so the generator
  exercises the same constraints real work does. A generator that bypasses the
  schema would happily produce nights the system cannot actually create.
- **Failures are generated too.** A night with no failures is not a realistic
  night, and the failure ledger is a view a judge may well look at.

## Impact

**New:** `packages/seed/` and its tests.

**Changed:** nothing. The generator writes through existing interfaces and adds
no requirement to any other capability.

**Risk:** generated data that is structurally wrong would be discovered only when
the scrubber renders it — weeks later, after the scrubber was built against it.
Mitigated by writing through the repository layer and by asserting the generated
night satisfies the same queries the real night view will use.
