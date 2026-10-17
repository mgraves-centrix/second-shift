# What the first real scoring found

## Scale classification

**L2 — Feature.** Three capabilities — `telemetry`, `operations` and `evals` —
each with one component, under a day of work apart from the measurement it
unblocks. It adds a refusal to a command whose refusals are themselves a
specified requirement and changes what a backup is required to hold, so it needs
spec deltas rather than tasks alone. No migration: every column it fills has
existed since `0001_initial.sql`.

Three pieces of it would be L0 on their own — they restore behavior an ADR or a
requirement already promised — and are recorded here because they were found
together and the spec text has to change with them:

- `model_call_payloads` was in the first migration so that capture would start
  on day one (ADR 0007). Nothing ever called its insert.
- `eval_results.output_path` has existed since the base schema. Nothing wrote it.
- A backup prints that it holds "every recorded model payload". It held none.

## Why

On 16 Oct the first scoring against a real checkpoint ran on the always-on
machine (`docs/operations/reports/2026-10-16-machine-session.md`). The judge
refused 1 of 18 samples against the week-1 brain and 2 of the first 5 against
the week-8 one, every time at the same character offset. Four things about the
instrument turned out to be wrong beyond the refusals themselves.

**A refused judgement could not be read back.** The table that exists to keep
what a model said had never held a row, and the failure recorded for the sample
named neither the judge's call nor the answer it was judging. Six reproduction
attempts all parsed, so the cause is still a hypothesis drawn from an offset.

**A run that lost one sample could never be completed.** `score` generates
every sample from scratch, and `eval_results` is unique per sample, so a second
pass died with a raw `IntegrityError` on the first sample already recorded. A
run killed partway reads as "awaiting scoring" — so that crash was the obvious
next step — and the week-1 baseline is the one run in this system that cannot
be retaken. At the observed refusal rate, scoring it was close to a coin flip
against destroying it.

**The judge's prompt was pinned by nothing.** `eval_runs` records the judge's
model and a configured version string. The text the judge is asked is in code
and hashed nowhere, and the curve compared judges by name alone. The obvious fix
for the refusals is an edit to that text, and two runs scored either side of the
edit would have passed every refusal the curve had while having been measured by
different instruments. The generating agent's prompt was pinned this way from
the start (`architect.v1:<sha>`); the judge's was the asymmetry.

**`status` and `score` read their content relative to the working directory.**
Run over SSH on the machine — the one place they are meant to run — `status`
died with a traceback naming `config/evals/rubric.md`.

## What this change is not

- **Not a looser parse.** `ENDGAME.md` says a refused judgement on a real
  checkpoint is a finding about the prompt, and `Judgement.parse` and
  `last_object` are unchanged. The fix to the ask is chosen from the refused
  text once it can be read, not from the offset.
- **Not a retry.** A refused sample stays refused. Re-asking the judge until it
  produces something parseable would select for the answers it can grade.
- **Not a migration.** Every column used here exists already.
- **Not a training pipeline.** Payloads are kept so the option ADR 0007
  preserves stays real, and so a failure can be diagnosed. Nothing reads them
  for training.

## What changes

1. **Every completion keeps what it said.** `Reasoner.complete` hands the
   messages, the completion and its finish reason to `Recorder.record_payload`,
   which writes both halves beside the database under a month directory and
   then records the row. A write that fails records a failure and the caller
   still gets its answer.
2. **A backup carries the payloads**, with no default for where they are, so a
   caller cannot write one that omits them while saying it holds them.
3. **A refused judgement names the calls it can be read back from**, and a
   scored result points at the answer it scored.
4. **A run is scored once.** A run holding any result is refused before
   anything is generated, and `status` names an interrupted run as one.
5. **The judge is pinned by what it asks.** Its recorded version carries the
   hash of its ask, and the curve refuses two versions as two instruments.
6. **The ask is fixed from evidence**, measured before and after on a copy.
7. **The week-8 measurement runs**: a fresh week-8 baseline, both runs scored
   in one sitting under the pinned judge, and the curve's verdict or refusal
   recorded.
8. **The commands find their content from anywhere.**

## Resolved before writing

**Fix the judge, or score as it stands.** Put to the subject on 16 Oct with
both options and their costs. Resolved 17 Oct: fix and pin the judge first, then
score both runs under it. Recorded here so it is not re-asked.

## Impact

- `apps/api/secondshift/telemetry/` — `payloads.py`, `Recorder.record_payload`
- `apps/api/secondshift/providers/base.py` — the one caller
- `apps/api/secondshift/ops/` — backup, restore, the command
- `apps/api/secondshift/evals/` — judge, runner, the command
- `apps/api/secondshift/config.py` — `SECOND_SHIFT_PAYLOADS`
- `deploy/spark/second-shift-backup.user.service`
- `docs/operations/RECOVERY.md`, and three documents whose derived count of the
  curve's refusals moves from ten to eleven

## Constitution Compliance

1. **The Brain Is Plaintext Under Git — compliant.** Payloads are not memory and
   are not written to the brain. The brain stays excluded from backups, named
   with its reason in every manifest.
2. **The Privacy Airlock — compliant, and this is the principle that governs
   the change.** Payloads hold raw, unredacted text, including `local-only`
   ideas. They are written on the machine that made the call, under the data
   directory, and nowhere else. No route reads them (`api-layer`'s requirement
   is unchanged). A backup carrying them stays under ADR 0014 — it never leaves
   the premises — and `deploy/judge/Dockerfile` copies an allowlist that cannot
   reach the payload directory. The judge stays `local-only` (ADRs 0010, 0015);
   nothing in this change lets a judgement leave the machine.
3. **No Empty Mornings — compliant.** A payload write that fails records a
   failure and returns the answer, so a full disk under the payload directory
   cannot cost a night.
4. **Text-First, Voice Layered On — not affected.**
5. **One Codebase, Two Deployments — compliant.** The payload root is
   configuration. A judge deployment never writes a payload in practice: the API
   makes no model calls (only the night and eval scoring do), and the night never
   dispatches a synthetic entry. Were one written, its training eligibility
   follows its model call's flag.
6. **Scope Boundary — not affected.** Nothing in `NOT_BUILDING.md`.
7. **Telemetry From Line One — compliant, and strengthened.** Capture is in the
   provider base class, so no backend can skip it, and a failure to write is
   itself recorded. `model_call_payloads` carries no `is_synthetic` column of its
   own; it references its `model_calls` row one to one, which does, and
   `training_eligible` is derived from it.

## Risk

- **Disk.** Completions run to 12,000 tokens. At the current rate — a night is
  tens of calls, a scoring run thirty-six — that is megabytes a week. Nothing
  bounds it yet; `retention_class` exists for the day something must, and that
  is recorded as open rather than solved here.
- **The fix to the ask could change what the judge scores, not only whether it
  parses.** That is why the ask is pinned before it changes, and why both
  week-8 runs are scored under the same ask rather than one under each.
