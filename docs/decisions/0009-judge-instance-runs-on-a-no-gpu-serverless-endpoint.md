# 0009 — The judge instance runs on a no-GPU Serverless AI Endpoint

**Status:** accepted · **Date:** 2026-09-02

## Context

ADR 0004 assigned the judge instance to "Nebius hosting" and recorded an open
risk against it: whether Nebius Serverless Endpoints can host a web
application rather than only serving models. The spike meant to answer it,
scheduled for day 5 of week one, never ran. `2026-09-02-add-nebius-executor`
inherited the question as a `[NEEDS CLARIFICATION]` marker, submission-
blocking — without a hosting target there is no judge instance to
demonstrate.

The marker's first resolution answered on the wrong premise: it asserted
Serverless Endpoints only serve models and reached for a generic container or
VM target instead. Reading Nebius's own Endpoints and Jobs documentation side
by side, rather than trusting that assumption, showed otherwise — both run an
arbitrary container on a Compute container VM, and both creation flows offer
the identical choice to omit a GPU. That correction is what this ADR records.

## Decision

The judge instance runs as a **Nebius Serverless AI Endpoint, on a no-GPU
container VM** — the same product ADR 0004 already named, running this code
on the `cloud` profile per Principle 5, not a generic VM reached for because
the Nebius product was assumed unable to do it.

The models the judge instance calls are a separate question from where it
runs. It calls Token Factory per-token, the same as the personal instance
under `cloud-assisted` policy; hosting the process on a Nebius Endpoint does
not route its model calls through that endpoint.

## Rationale

**The premise that blocked this was untested, and testing it reversed the
conclusion.** Nebius's Endpoints documentation describes deploying "as an
interactive endpoint or as a non-interactive job," both running an arbitrary
container on Compute container VMs. Both the Endpoints and Jobs creation
flows show the same line — "Select whether the VM should have GPUs" — with a
VM lacking one a supported configuration, not a hypothetical. ADR 0004's open
risk closes as answered, not deferred to the fallback it named.

**The cost argument survives with real numbers in place of an assumption.**
Compute bills a non-GPU VM at $0.012 per vCPU-hour and $0.0032 per GiB-hour. A
`2vcpu-8gb` preset run continuously — 730 hours, a full month — costs
`2 × $0.012 × 730 + 8 × $0.0032 × 730 ≈ $36`. The same month on the H100
dedicated endpoint the pricing extract of 27 Aug priced at $4.05/hr, run the
same way, is `730 × $4.05 ≈ $2,957` — GPU rates for a process with no GPU work
in it.

**Hosting the judge instance on Nebius, rather than around it, is the sharper
demonstration.** ADR 0004's own context names why this matters: judging
weighs how effectively Nebius is used. A Nebius-native Endpoint makes that
visible in a way a generic outside compute target would not.

**Preemptible pricing is not available here, and it does not need to be.**
Nebius reserves preemptible VMs for GPU platforms; a no-GPU VM only supports
the regular type. A judge instance cannot tolerate being preempted mid-demo
regardless of what pricing tier is available.

**The demo-window GPU rental ADR 0004's open-risk note first reached for
stays available, narrowed to what it is actually good for.** An hourly
dedicated endpoint is real infrastructure for a known demo window with hard
latency requirements. It is rejected as the default because judges arrive
unpredictably across a multi-day submission window, and an hourly endpoint
bills for the idle between them.

## Consequences

- ADR 0004's open risk is answered, not left as an unresolved bullet:
  Endpoints can host the application. This ADR supersedes that bullet without
  editing it — the record of what was open, and for how long, stays visible
  in 0004 itself.
- `2026-09-02-add-nebius-executor`'s judge-deployment marker resolves against
  this decision rather than the incorrect one it first recorded.
- The judge instance's deploy target is now concrete enough to build
  against — a container image, published to the endpoint, no GPU preset
  selected.
- Cost is bounded and known before implementation, not discovered at deploy
  time: roughly $36/month sustained, against roughly $2,957/month for the
  GPU-endpoint alternative this replaces.
