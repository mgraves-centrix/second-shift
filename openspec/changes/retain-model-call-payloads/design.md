# Design — retaining model call payloads

## Context

See `proposal.md` — *Why*. What matters here is the shape of what already
exists:

- `Reasoner.complete` in `providers/base.py` is the single concrete path every
  completion takes. It holds the messages, the raw completion text, the
  `redaction_applied` flag and the `model_call_id` it just recorded, together,
  in one scope. No other place in the system holds all four.
- `artifacts/store.py` already solves the same problem for artifacts: a
  configured root, a relative path in the row, bytes read back after the write,
  and a raise before any row exists on failure. It is the pattern to copy.
- `model_call_payloads` has every column this needs and has had since
  `0001_initial.sql`. No migration.
- `Recorder` owns the single writer lock. File I/O must not be inside it.

A design document for a change this size is here because the change is
cross-module — providers, telemetry, evals, ops — and because two of its
decisions are genuinely arguable and should be argued before the code exists.

## Goals

- Retention that an implementation cannot opt out of.
- A payload row that is never written for a file that is not there.
- A backup whose printed claim about payloads is true.

## Non-Goals

- **Pruning or retention-class enforcement.** `retention_class` exists in the
  schema with a default of `standard`; nothing reads it, and nothing in this
  change starts. Writing a pruner now would be the untested machinery that the
  defect this change closes is an instance of.
- **A reader.** Nothing in this change surfaces payload text anywhere.
  `api-layer` forbids a route reading the table, and that stays true.
- **Backfill.** It is not possible, which is the whole argument. The six nights
  already run stay unreadable.
- **Retaining tool calls or transcriptions.** `tool_calls` stores a redacted
  query by requirement, and the transcription path has no payload table.

## Decisions

### 1. Retention happens in the provider base class

**Chosen** because the base class already owns telemetry for exactly this
reason, stated in its own docstring: *"An implementation that forgets to record
telemetry is not possible, because it never writes any — the base class does."*
Retention is instrumentation; the argument transfers unchanged.

*Alternative: each call site retains what it cares about.* Loses because it is
the defect. `insert_model_call_payload` was available to every call site for
seven weeks and no call site used it. A capability every caller may use is a
capability no caller uses.

*Alternative: the recorder retains inside `record_model_call`.* Loses because
`record_model_call` does not receive the text, and giving it the text would put
prompt content into the signature every synthetic seed path also calls — a
wider blast radius for no gain.

### 2. Both policies are retained, and `redacted` says which

**Chosen.** ADR 0007's argument is that a night that runs before retention
exists is permanently untrainable, and a `cloud-assisted` night is as
untrainable as a local one. What is stored for a cloud-assisted call is what was
actually sent, which had already passed the redaction step, so `redacted`
carries that distinction into the row.

*Alternative: retain `local-only` calls only.* Loses twice. It discards half the
evidence for a trend the submission rests on, and it makes the retained set a
function of policy — so a reader comparing two nights could not tell a missing
payload from a cloud-assisted stage. The privacy position does not need it
either: the content of a cloud-assisted call has already left the machine, so
keeping a local copy adds no egress, and the constitution's violation list names
*an export path that includes `model_call_payloads`*, not its existence.

### 3. A retention failure is recorded, not raised

**Chosen.** The completion is the product; the payload is evidence about it. A
full disk at 2am should cost the evidence and nothing else. It is recorded as a
typed failure through the recorder, so the gap is visible in the failure ledger
rather than inferred later from an absent row.

*Alternative: raise, as `write_artifact` does.* Loses because the artifact case
is not analogous: there, the file **is** the product, so a row describing a file
that does not exist is a lie about the deliverable. Here the deliverable is
already in the caller's hands.

*Alternative: swallow it.* Loses to Principle 7 — unrecorded, this is sampled
instrumentation, and the sample is biased precisely toward the nights that went
wrong.

### 4. `output_path` points at the retained completion of the generating call

**Chosen** because that file *is* the scored output, and the column already
exists for it. A reader of a score gets to the text without a join.

*Alternative: leave `output_path` NULL and let readers join through
`model_call_id`.* Loses on the only use that matters: somebody checking a
submission's number should not have to know the payload path convention.

*Alternative: write the output a second time under the eval's own tree.* Loses
— two copies of the same bytes that can disagree.

### 5. The root is configured, and the row stores a relative path

`SECOND_SHIFT_PAYLOADS`, defaulting to `~/second-shift-data/payloads`, beside
`SECOND_SHIFT_ARTIFACTS`. Registered in `config.py` so `config show` reports it;
a setting the resolver does not know about is a setting `ops` and `config` can
disagree about, which is the disagreement that makes a backup of the wrong
directory look successful.

Layout `<yyyy-mm>/<model_call_id>.prompt.json` and `.completion.json`: month
directories keep one night's files findable by hand and keep any single
directory from growing without bound, and the call id is already unique and
already sorts by time.

## Risks / Trade-offs

- **Payload volume on the always-on machine.** → The schema anticipated it
  (text on disk, not in SQLite). `ops doctor` reports disk; pruning is a
  non-goal and stays one until a real number says otherwise.
- **A backup gets larger and slower.** → It is a tree copy beside one that
  already runs; the manifest counts it so the cost is visible rather than
  surprising.
- **A judge deployment would retain its visitors' prompts.** → It writes them
  marked ineligible for training, under its own root, and
  `check-judge-package.py` already refuses to *ship* a database carrying payload
  rows, so nothing travels. Worth stating because it is the one direction this
  change could have leaked.
- **`redacted` is only as honest as `redaction_applied`.** → It is passed by the
  caller today. This change does not make that worse, and recording the flag is
  what makes a wrong one findable.

## Migration Plan

None. No schema change, no data move. Deployment is `deploy.sh`; the payload
root is created on first write. Rollback is reverting the code — the rows and
files already written stay readable and harm nothing.
