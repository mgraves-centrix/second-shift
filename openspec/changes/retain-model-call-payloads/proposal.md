# Retain model call payloads, and make a backup carry them

**Scale: L2 — Feature.** Cross-module (providers, telemetry, evals, ops) but one
sitting, and it introduces no new pattern: payload writing mirrors
`artifacts/store.py` line for line, and the backup change extends a tree copy
that already exists. Proposal, specs and tasks; no design doc, because there is
no trade-off here that is not already argued in ADR 0007.

## Why

`Repository.insert_model_call_payload` exists, is complete, and **has no caller
anywhere in the repository — not in the orchestrator, not in a test.**
`model_call_payloads` has never held a row, after six real nights and an eval
run. The 16 Oct machine session found it and named it first of five
recommendations; this is the same defect as `close_run has no caller`, found
2 Sep.

It costs three things that matter this week:

- **The tool lies to the operator.** Every backup prints *"this archive holds
  unredacted captured text and every recorded model payload"*. There are none —
  and grounding this proposal found a second hole behind the first:
  `create_backup` copies the database and the artifacts root only, so even once
  payloads exist a backup would still not carry them. `openspec/specs/operations`
  already *requires* that a backup contains "every recorded prompt and
  completion". It never did.
- **`eval_results.output_path` is NULL for all 17 scored samples.** The
  submission's centerpiece ships with numbers and nothing to read behind them.
- **It is why the 16 Oct judge failure could not be diagnosed.** The failing
  judgement was not kept, so the only evidence was a character offset.

ADR 0007's argument is that this cannot be backfilled: a token count cannot be
reconstructed into a prompt, so every night that runs before retention exists is
permanently untrainable. Four nights remain before the deadline.

## What Changes

- Every completion recorded by `Reasoner.complete` also retains its prompt and
  its completion text on disk, with a `model_call_payloads` row pointing at
  them. Retention happens in the provider base class, for the reason the base
  class records telemetry: an implementation cannot forget what it never writes.
- A new payload root, `SECOND_SHIFT_PAYLOADS`, registered beside
  `SECOND_SHIFT_ARTIFACTS` and reported by `config show` like every other
  setting.
- `training_eligible` carries the synthetic exclusion, because
  `model_call_payloads` has no `is_synthetic` column and the schema comment says
  synthetic data never enters a training set. `redacted` records whether what
  was stored had been through the redaction step.
- A payload write that fails records a typed failure and no row, and **does not
  fail the completion**. The completion is the product; the payload is evidence.
- `eval_results.output_path` is written from the retained completion of the
  generating call, which is what the column is for.
- A backup copies the payload tree, counts it in its manifest, and a restore
  restores it — so `CONTAINS` becomes a true statement rather than an intention.

## Capabilities

### New Capabilities

None. Every requirement here belongs to a capability that already exists.

### Modified Capabilities

- `telemetry`: ADDED — a completion's prompt and completion text are retained
  beside the cost row, by the provider base class, and a retention failure is
  recorded without losing the completion.
- `operations`: MODIFIED — *A backup carries the evidence needed to check a
  restore* and *A backup never leaves the machine's trust boundary* gain the
  scenarios that would have caught the payload tree being absent from both the
  copy and the manifest.
- `evals`: MODIFIED — *A score records the model call that produced what was
  scored* gains the scenario that the result also points at the retained output,
  so a number in the submission can be read back to the text it graded.

## Impact

- `apps/api/secondshift/telemetry/payloads.py` — new; the path convention, the
  root, and the write-then-read-back.
- `apps/api/secondshift/telemetry/recorder.py` — `record_model_call_payload`:
  file write outside the writer lock, row insert inside it.
- `apps/api/secondshift/providers/base.py` — `Reasoner.complete` retains after
  recording. The one call site that covers every provider.
- `apps/api/secondshift/config.py` — `ENV_PAYLOADS` beside `ENV_ARTIFACTS`.
- `apps/api/secondshift/evals/runner.py` — `_record_result` writes
  `output_path`.
- `apps/api/secondshift/ops/backup.py`, `restore.py`, `__main__.py` — the
  payload tree copied, manifested, restored and reported.
- `docs/operations/RECOVERY.md`, `docs/DATA_MODEL.md` — the claims that were
  false become true, and say which.
- No migration. The table and every column it needs have existed since
  `0001_initial.sql`; what was missing was the caller.

## Constitution Compliance

| Principle | Outcome |
|---|---|
| 1. The brain is plaintext under git | **Not engaged.** Payloads are model prompts and completions, not brain state. The backup's `EXCLUDED` entry for the brain is untouched. |
| 2. The Privacy Airlock | **Governs this change, and passes.** No egress path is created. The table stays unreachable from any route (`api-layer` already requires that), `scripts/check-judge-package.py` already refuses a database carrying any payload row at all, and the seed writes `model_calls` through the repository rather than through a `Reasoner`, so a packaged judge database still has zero payload rows. Retention covers both policies — a `cloud-assisted` night is as untrainable without it as a local one — and `redacted` records which it was. The backup change keeps payloads inside the boundary that already refuses an off-premises destination. |
| 3. No empty mornings | **Not engaged.** |
| 4. Text-first, voice layered on | **Not engaged.** |
| 5. One codebase, two deployments | **Passes.** The path stored is relative to a configured root, as artifacts already are, so the judge deployment runs the same code against its own root. An absolute path in a row would pin a home directory into data a judge reads, which `scripts/check-no-environment.sh` exists because of. |
| 6. Scope boundary | **Passes.** Retention of what the system already generated. No new surface, no new agent, nothing the user interacts with. |
| 7. Telemetry from line one | **This change exists to satisfy it.** A payload write that silently failed would be the sampled instrumentation the principle forbids, which is why a failure is a recorded `failures` row rather than a swallowed exception. The synthetic exclusion rides on `training_eligible`, the column the schema designates for it. |
