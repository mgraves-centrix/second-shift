# 0004 — What runs on Nebius

**Status:** accepted · **Date:** 2026-08-27
**Superseded in part by [0009](0009-judge-instance-runs-on-a-no-gpu-serverless-endpoint.md)** — the
open risk in *Consequences* is closed. The bullet is left as written: how long a
risk stayed open is part of the record.

## Context

Hackathon rules require the project to run on Nebius and use at least one NVIDIA
open-source model. Judging weighs *how effectively* Nebius and Nemotron are
used. A split chosen to satisfy a rule reads as compliance; a split chosen on
engineering merit reads as a system.

## Decision

**Always local, every profile:** capture, ASR, transcript storage, embedding and
retrieval, redaction and policy resolution, the orchestrator and all database
writes, the UI, and all reasoning for `local-only` entries.

**Token Factory:** the research-synthesis, architect, and critic turns on
`cloud-assisted` entries. Long-context, high-quality-bar work where a small
local model is genuinely the wrong tool.

**Serverless Jobs:** the build stage, fanned out to 3–5 parallel variants, one
Job each, ranked afterward by the critic into a `variant_group`. Also nightly
eval runs.

**Nebius hosting:** the judge instance, running the `cloud` profile.

## Rationale

Retrieval stays local unconditionally because that is the Airlock invariant —
only assembled, policy-filtered context is ever eligible to leave.

Parallel variant generation is the strongest available use of Serverless Jobs
because it is something the Spark *cannot* do: one box cannot run five builds
concurrently at speed. The parallelism is why the artifact is better, which
makes the Nebius dependency real rather than decorative.

## Consequences

- The demo shows two ideas side by side: a `local-only` artifact at $0.00 cloud
  spend, and a `cloud-assisted` artifact that fanned out to five Nebius Jobs.
  Both numbers are read from `model_calls`.
- Variant fan-out fills the `variant_group` / `variant_rank` columns the design
  already called for.
- **Open risk:** whether Nebius Serverless Endpoints can host a web application
  rather than only serving models. Spiked on day 5 of week one. If not, the
  judge instance needs a container or VM target.
