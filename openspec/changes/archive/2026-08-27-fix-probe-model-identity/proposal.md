## Why

The capability probe checks whether a port answers, not what answers.

On 2026-08-27 the Spark was found serving `Qwen/Qwen3.8-27B-FP8` through vLLM on
port 8000 — the exact port the probe treats as the local reasoner. Run at that
moment, the probe reported `local_reasoner: available`, the profile resolved to
`spark`, `local-only` was reported available, and every local-only reasoning
call would have routed to a non-NVIDIA model.

Silently. `model_calls.model` records the identifier the caller intended, not
the one that replied, so the telemetry would have agreed with the mistake rather
than exposed it. The failure is invisible by construction.

Two things make this worse than a normal bug. It is a hackathon rules violation
— no third-party models in the runtime path — reached without anyone doing
anything wrong. And it is environment-dependent: the same probe correctly
reported *unavailable* an hour earlier, before that container started.

The spec is what is wrong, not the implementation. It says the probe checks
"local inference endpoint reachability", and the code checks exactly that.
Reachability was the wrong contract.

## What Changes

The probe asks a reachable endpoint **which model it is serving** and compares
that against the expected local binding. Three outcomes instead of two:

- reachable, serving the expected model → available
- unreachable → unavailable, as today
- reachable, serving something else → **unavailable, naming what it found**

The third outcome is the point. It must be unavailable rather than available,
and its reason must name the model actually found, because "something is
listening on 8000" and "the local reasoner is up" are different facts that this
system had been treating as one.

The expected model name is configuration, not a constant — the local
`--served-model-name` is chosen at serve time and belongs beside the other
model bindings.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `compute-profiles`: the probe verifies served model identity, not endpoint
  reachability.

## Constitution Compliance

| Principle | Status | Note |
|---|---|---|
| 2. Privacy Airlock | **Strengthens** | `local-only` currently becomes available whenever any process holds port 8000. A local-only idea would be routed to an unverified model that happens to be listening. |
| 5. One codebase, two deployments | Compliant | The check lives in the probe, behind the same interface, on every profile. |
| 7. Telemetry from line one | **Strengthens** | Removes a case where recorded telemetry would corroborate a wrong routing decision instead of revealing it. |

No violations. Two principles are strengthened: this closes a path by which the
Airlock could be satisfied on paper while being false in fact.

## Impact

**Changed:** `secondshift/config.py` — the endpoint check and its `Capability`
detail string. `probe()` gains an expected-model parameter.

**Not changed:** profile resolution, the capability report, quarantine. They all
consume the probe's findings and inherit the fix.

**Risk if deferred:** Spike B stands a vLLM server up on port 8000 tomorrow. The
first thing the probe would validate is an endpoint whose identity it cannot
check — so the spike's own result would be untrustworthy for the same reason.

## Scale

L2. One capability, one requirement modified, no new architecture, no design
document. Small — but it is a spec change rather than a bug fix, because the
implementation already matches the requirement as written.
