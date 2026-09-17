## Scale

**L2 — Feature.** One capability, local only, touching files nothing else owns:
a gate script, a mutation runner, a browser test and a workflow. No design doc —
both open decisions were settled by measurement, recorded below.

## Why

There was no CI. Every gate was run by hand in a remembered order, and the one
browser check of the scrubber lived in a scratch directory. The suite's coverage
of the wrong things was unmeasured, and the record already held a case of a test
passing against a wrong implementation: lanes rebuilt from invoked events passed
because every lane in the fixture held one.

That case was still open. The first run of the mutation check found the lanes
defect caught by nothing.

## What Changes

- `scripts/gate.py` runs every gate in order and exits with the first failing
  gate's code. It is the only definition of the gate set.
- `.github/workflows/gate.yml` installs tools and calls it. No secrets, no deploy.
- `apps/web/e2e/` seeds a night into a fresh database, serves it from a real
  orchestrator on a free port, and drives the installed Chrome through
  `playwright-core`, asserting rendering from geometry.
- `scripts/check-mutations.py` reintroduces eight shipped defects and requires
  the gate for each to fail.
- The two check scripts resolve the repository from their own location and use
  `git -C`, so they no longer change directory.
- A test for the lane roster closes the gap the mutation check found.

## Decisions, by measurement

**What CI runs.** The existing gate set measured 36.4s end to end. With the
browser test (1.9s) and the mutation check (8.3s) the whole gate is 46.3s.
Everything runs on every push: a split would save under a minute and create a
second definition of passing.

**Mutation testing or a discipline.** Neither as posed. A mutation tool over
seven hundred tests is slow and reports mutants nobody would write; "every test
was shown to fail once" cannot be enforced. The choice is a short list of
defects that actually shipped, re-run on every push, where a mutation whose
target moved fails rather than silently stops applying.

## Constitution Compliance

| Principle | Status | Note |
|---|---|---|
| 1. Brain plaintext under git | Not applicable | |
| 2. Privacy Airlock | **Implements** | The airlock and redaction tests are the first gate, and two of the mutations reintroduce airlock defects. |
| 3. No empty mornings | Not applicable | |
| 4. Text-first | Not applicable | |
| 5. One codebase, two deployments | **Constrains** | The gate runs identically on a laptop, in CI and on the always-on machine, from any directory. |
| 6. Scope boundary | Compliant | CI deploys nothing and holds no credential. |
| 7. Telemetry from line one | **Implements** | One mutation removes a failure's run attribution and must be caught. |

No violations.
