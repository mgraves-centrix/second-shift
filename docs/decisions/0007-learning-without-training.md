# 0007 — Learning happens in the brain, not in the weights

**Status:** accepted · **Date:** 2026-08-27

## Context

"It gets better at being me" is the central claim. The question is whether that
improvement comes from accumulated context or from updated model weights.

## Decision

**The core loop does not train weights.** Improvement comes from the brain:
retrieval over accumulated markdown, tracked decisions feeding subsequent runs,
and the failure ledger consulted at planning time.

**One narrow fine-tune is permitted, and only one:** a LoRA on the *interviewer*
agent, no earlier than week 7, strictly optional, on Nebius AI Cloud compute.
It may never become a dependency of the demo.

**Payload capture starts on day one regardless**, so the option survives even if
it is never exercised.

## Rationale

**Legibility.** `git diff week1..week8` over the brain is a human-readable
artifact a judge understands on sight. A weight delta is the least visible form
of learning there is, and the centerpiece demo depends on improvement being
*visible*.

**Attribution.** The eval spine pins `judge_model` and `rubric_sha` precisely so
that an improving curve measures the brain rather than judge drift. Changing
policy weights at the same time introduces a second moving part and destroys the
attribution. The measurement design and weight training are in direct tension;
the measurement design wins.

**Data shape.** Roughly 600 entries by week eight, of which a few hundred carry
outcome labels. Thin for tuning a 30B MoE, and the signal is preference — "this
was kept" — rather than demonstration, which is the harder thing to learn from.

**Schedule risk.** A fine-tune plus a regression harness is a week of work in a
nine-week solo build, competing directly with the video and the scrubber. A
failed or regressive tune in week seven has no recovery path.

## Why the interviewer is the exception

The label already exists and is unusually clean: `decisions.status = 'decided'`
means the question was worth asking; `deferred` or `obsolete` means it was not.
Binary preference data on question quality, accumulating from the first week of
dogfooding, on the one agent that *is* the product.

Training it on Nebius AI Cloud compute also adds a third Nebius surface beyond
Token Factory and Serverless Jobs, which is directly scored.

A cheaper week-4 version captures much of the benefit with none of the risk:
automatic few-shot selection, pulling the highest-rated past questions into the
interviewer's context. Learning from results without touching a weight.

## Consequences

- `model_call_payloads` captures prompt and completion text from day one.
  `model_calls` records what a call *cost*; this records what it *said*. A token
  count cannot be reconstructed into a training example, so any night that runs
  before this exists is permanently untrainable.
- Text lives on disk, referenced by path. Contexts run to 1M tokens; payloads
  would otherwise outweigh every other table combined within weeks.
- `decisions.raised_by_invocation_id` links a question to the interviewer
  version that asked it. `agents` was versioned specifically to attribute
  quality shifts to prompt revisions, and without this link that attribution was
  impossible for the most important agent in the system.
- `interviewer_training_pairs` materializes the dataset from data already being
  collected, so the option is demonstrably live rather than theoretical.
- **Privacy:** `model_call_payloads` holds raw unredacted content for local-only
  ideas. Local by construction, excluded from "export your brain" by default,
  never synced and never present in a judge deployment.
