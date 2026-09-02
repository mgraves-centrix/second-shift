## Context

See `proposal.md` — Why. Only the state that shapes the approach follows.

`Repository.insert_agent(name, role, version, prompt_path, prompt_sha, ...)`
exists and has never been called outside a test fixture, which passes
`deadbeef` against a path that does not exist. `Recorder.invocation(agent_id,
run_id=, stage=)` opens and closes the invocation row and derives parentage and
depth from a `contextvar` (ADR 0008). `Reasoner.complete(messages, policy=,
effort=)` records the model call in its base class.

The `agents` table already carries everything needed, including a six-value
`role` CHECK and `UNIQUE(name, version)`. No migration.

The served model wraps reasoning in `<think>...</think>` inside `content`, with
no parser configured — verified against the live server on 2 Sep.

## Goals / Non-Goals

**Goals:**
- Six prompt files, versioned in the filename, marked as drafts.
- Registration that computes the hash, refuses a missing file, and refuses an
  edited file at a version already recorded.
- One invocation path from a role to a recorded model call, reusing the
  recorder and the reasoner rather than reimplementing either.

**Non-Goals:**
- Sequencing agents. That is `night-pipeline`.
- Choosing context for an agent. It takes what it is handed; `retrieval`
  assembles.
- Any framework — no graph, no router, no tool loop.
- Deciding what the prompts say.

## Decisions

**Prompt versioning: the filename is the version, and files are immutable.**
Full argument in `proposal.md`. Restated as mechanism: `prompts/<role>.v<n>.md`;
registration reads the highest version present for each role, computes its hash,
and compares against any row already recorded for that `(name, version)`. Equal
means already registered — registration is idempotent. Different means the file
was edited in place, which raises naming both hashes.

Alternatives considered:
- *Manual `version`, sha recorded only for the record.* Rejected — `(name,
  version)` is the natural grouping key for the eight-week curve, and it would
  silently merge two different prompts.
- *Auto-increment the version when content changes, keeping one filename.*
  Rejected — the file on disk would say one thing and the row another, and the
  question "which text produced this invocation" would need a database lookup
  to answer instead of a filename.

**Chain-of-thought is stripped at the agent layer, not the provider layer.**
`VllmReasoner` deliberately returns the completion whole, because a marker
splitter that guesses wrong deletes the answer and corrupts token accounting.
The agent layer is a different position: telemetry has already counted the
completion by then, so trimming affects only what the caller renders. The strip
is on the literal `</think>` delimiter the model emits structurally; if it is
absent the text passes through untouched, so a model that stops emitting it
degrades to verbose output rather than to an empty brief.

Alternatives considered:
- *Instruct only, strip nothing.* Rejected on evidence — the live model emitted
  the wrapper anyway on a trivial prompt.
- *Strip in the provider.* Rejected — `local-inference` argued that case and
  decided against it; reopening it here would trade a correct decision for
  convenience at the wrong layer.

**`max_tokens` is per-role configuration.** The model deliberates inside the
budget: at 200 a one-sentence question returned reasoning and no answer. A
critic needs less room than an architect, and neither number belongs in Python
— they go in `config/models.toml` beside the sampling settings already there.

**Registration is idempotent and runs at startup.** Called twice with unchanged
files it writes nothing the second time. This is what makes it safe to call
from a process that restarts, and it is why the hash comparison is a refusal
rather than an insert.

## Risks / Trade-offs

- **A draft prompt is still a prompt, and an eight-week curve started against
  drafts measures the drafts** → Mitigated by marking every file as a draft in
  its own text, and by the versioning decision: replacing a draft with the
  subject's own words is `v2`, visible in the curve at exactly the point it
  happened rather than blurred into it.
- **Stripping `</think>` could hide a model that has started emitting something
  else** → The strip is conditional on the delimiter being present, so a change
  in model behavior shows up as verbose briefs, which is noticeable, rather than
  as empty ones, which is not.
- **Idempotent registration hides a prompt file that was reverted rather than
  superseded** → A revert restores the original content, whose hash matches the
  recorded row, so registration correctly treats it as unchanged. That is the
  intended reading: the pinned thing is content, not history.

## Migration Plan

No schema migration. The test fixture writing `deadbeef` against a nonexistent
path is replaced with registration against the real files; that fixture is the
only existing caller, so nothing else changes shape.
