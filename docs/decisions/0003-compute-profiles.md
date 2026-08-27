# 0003 — Compute profiles, not a Spark dependency

**Status:** accepted · **Date:** 2026-08-27

## Context

Building against one specific piece of owned hardware produces something only
one person can run. The question that prompted this: *"while I have a Spark, not
everyone will — how do we make this attainable for other users afterwards?"*

## Decision

All compute sits behind four interfaces — `Transcriber`, `Reasoner`, `Embedder`,
`Executor`. A **compute profile** (`spark` | `workstation` | `cloud`) binds them
to implementations, resolved from `SECOND_SHIFT_PROFILE`, else a boot-time
capability probe, else `cloud`.

`local-only` policy is **unavailable** on the `cloud` profile. The UI states
this rather than silently downgrading the policy and sending the idea to a
remote model anyway.

## Consequences

- **Local-only is a hardware capability, not a preference.** This is the honest
  version of a privacy claim and a stronger one than a toggle.
- The judge demo instance is the `cloud` profile in a container — portability
  work and submission work become the same work.
- Anyone can run Second Shift without a Spark, at reduced privacy guarantees
  that the product names out loud.
- Cost: an indirection layer written on day one, before there is more than one
  implementation of anything. Accepted — retrofitting it later would touch every
  call site.
