## 1. The prompt files

- [ ] 1.1 Create `apps/api/secondshift/agents/prompts/` and write six files —
  `interviewer.v1.md`, `researcher.v1.md`, `architect.v1.md`, `builder.v1.md`,
  `critic.v1.md`, `distiller.v1.md`. Every file opens with an explicit
  draft marker naming that its content awaits the subject's judgment. Verify
  the six roles match the `agents` table's CHECK constraint read from the
  migration, not a hand-written list.
- [ ] 1.2 Each prompt instructs the model to close its reasoning before
  answering, given the live model wraps it in `<think>...</think>` inside
  `content`. Verify by asserting each file mentions the closing instruction, so
  a prompt rewritten later cannot silently drop it.

## 2. Registration

- [ ] 2.1 Implement `agents/roster.py` with the role-to-prompt mapping and a
  `register(repo)` that computes `prompt_sha` from file content via
  `hashlib.sha256`. Verify the recorded sha equals the file's hash for all six.
- [ ] 2.2 Raise a typed error when a prompt file is missing, writing no row.
  Verify with a test asserting both the raise and that `agents` is still empty.
- [ ] 2.3 Refuse a file whose content no longer matches the sha recorded for
  that version, naming both hashes. Verify with a test that registers, edits
  the file, re-registers, and asserts the raise.
- [ ] 2.4 Make registration idempotent: re-registering unchanged files writes
  no new rows. Verify by registering twice and asserting the row count is
  unchanged.

## 3. Invocation

- [ ] 3.1 Implement the invocation path: open `Recorder.invocation`, call the
  bound `Reasoner` with the policy passed explicitly, return the completion.
  No telemetry written in the agent. Verify with `grep -c "record_"` returning
  0 for the agents package.
- [ ] 3.2 Strip a trailing `</think>` boundary from the returned text, leaving
  the text whole when the delimiter is absent. Verify both directions with a
  stub reasoner: wrapped input is trimmed, unwrapped input is unchanged.
- [ ] 3.3 Add per-role `max_tokens` to `config/models.toml` and read it at
  invocation. Verify the configured value reaches the reasoner call.

## 4. Verification that can fail

- [ ] 4.1 **The sha is the load-bearing part.** Assert every registered agent's
  `prompt_sha` equals the hash of the file it names. Then hardcode the sha to a
  constant and confirm the suite goes red — if it stays green the pinning is
  decorative and `deadbeef` has been rebuilt with extra steps.
- [ ] 4.2 Assert a `local-only` invocation against a remote provider is refused
  at the call and writes no `model_calls` row.
- [ ] 4.3 Assert an invocation records its row with the expected run and depth.
- [ ] 4.4 Assert the six roles round-trip by enumerating the CHECK constraint
  from the schema rather than a literal list, so adding a seventh role to the
  database without a prompt fails the suite.
- [ ] 4.5 Replace the `deadbeef` test fixture with registration against the
  real files, and confirm the full suite still passes.

## 5. Against the real model

- [ ] 5.1 Make one real call through an agent against the Spark's reasoner over
  the tailnet, and paste what came back into the report. The suite must not
  depend on it.
- [ ] 5.2 Report whether the brief still opens with visible reasoning. If it
  does, say so plainly — that is the finding, not a detail to fix later.
