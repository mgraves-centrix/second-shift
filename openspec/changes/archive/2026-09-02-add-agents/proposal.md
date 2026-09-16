## Why

**Nothing in this system reasons in production, and the model is not why.**
`local-inference` shipped, the registry binds a real `Reasoner`, and
`nemotron-3.5-lightning` has served on the Spark for five days. Nothing calls
it, because there is no agent to do the calling. `docs/ARCHITECTURE.md`
specifies `agents/ roster + versioned prompt files`; the directory does not
exist.

`night-pipeline` cannot start without this — a checkpointed stage machine with
no agents has nothing to checkpoint — and `morning-interview` cannot either. It
is the narrowest thing between a working model and a working product.

There is also a measurement defect here, and it is the same one this project
already found once. `agents.prompt_sha` is `NOT NULL` so that an improving
eight-week curve can be shown to measure the brain rather than a quietly edited
prompt. The only thing writing that column today is a test fixture writing the
literal `deadbeef`, against `agents/prompts/researcher.v1.md` — a path that has
never existed. That is `reconcile-rubric-pinning`'s defect in a second place,
and it becomes permanent the moment a real invocation records it.

## What Changes

**Six versioned prompt files on disk**, one per role, named `<role>.v1.md`, and
**explicitly marked as drafts awaiting the subject's judgment**. What a prompt
says is a question for the person being assisted, not for whoever wrote the
code; `docs/prompts/AGENTS.md` says so directly, and the brain's seeded
`profile.md` already set the precedent of shipping a sketch that asks to be
corrected.

**A roster module** that registers each agent by reading its prompt file and
**computing `prompt_sha` from the file's content**. Never passed in, never
defaulted. Registering an agent whose prompt file is missing fails loudly: a
roster row pointing at a file that is not there is worse than no row.

**Prompt files are append-only, and the filename carries the version.** A
changed prompt is a new file at `v(n+1)`, never an edit in place. Registration
refuses a file whose content no longer matches the sha recorded for that
version — the same guard `reconcile-rubric-pinning` put on the rubric, for the
same reason. See "Decisions taken without a marker."

**An agent invocation path**: open the telemetry row through
`Recorder.invocation`, call the bound `Reasoner` with an explicitly passed
policy, and let the base classes record. The agent writes no telemetry itself
and knows `Reasoner`, not vLLM.

Not in this change: the night pipeline that sequences agents, retrieval (an
agent takes the context it is handed), a seventh role, or any agent framework —
no graph, no router, no tool-calling loop.

## Capabilities

### New Capabilities
- `agents`: the roster, its versioned prompt files, content-derived prompt
  pinning, and the invocation path from a role to a recorded model call.

### Modified Capabilities
(none — `telemetry`'s requirements already cover what an invocation records;
this is the first thing to actually produce one.)

## Impact

**New:** `apps/api/secondshift/agents/` (roster, registration, invocation);
`apps/api/secondshift/agents/prompts/<role>.v1.md` × 6.

**Changed:** `Repository.insert_agent` gains a caller. Test fixtures writing
`deadbeef` against a nonexistent path are replaced with registration against
real files.

**Not changed:** the schema. `agents` already has every column this needs,
including the `role` CHECK and `UNIQUE(name, version)`.

## Constitution Compliance

| Principle | Status | Note |
|---|---|---|
| 1. Brain plaintext under git | **Implements** | Agent prompts are versioned text under git, for the same reason the brain is. They do not move into the database; the database records which file and which content hash was used. |
| 2. Privacy Airlock | **Constrains** | An agent runs under a policy and passes it explicitly to `complete()`. It never reads a policy from ambient context and never defaults one. A `local-only` invocation reaching a remote provider fails at `assert_permitted` and again at the `model_calls` CHECK; no path is added that tries. |
| 3. No empty mornings | Compliant | An agent invocation is a unit that either records its work or records its failure. Sequencing and checkpointing belong to `night-pipeline`, and nothing here constrains how it commits. |
| 4. Text-first | Not applicable | No voice surface. The interviewer role's prompt is text; its speech layer is `morning-interview`'s. |
| 5. One codebase, two deployments | **Implements** | An agent knows the `Reasoner` interface. No provider specifics, no model identifiers in `.py` — bindings come from `config/models.toml` through the registry. |
| 6. Scope boundary | Compliant | Nothing in `NOT_BUILDING.md`. Six roles fixed by a database CHECK; no framework, no router, no chat surface. |
| 7. Telemetry from line one | **Implements, and is the point** | This is the first code that opens an `agent_invocations` row from something other than a test. The base classes already guarantee the writes; this change's job is not to route around them, and `prompt_sha` stops being `deadbeef`. |

No violations.

## Decisions taken without a marker

**A prompt change is a new version, and prompt files are never edited in
place.** `docs/prompts/AGENTS.md` posed this as an open decision — manual
versions with the sha merely recording what was used, or a changed file
automatically becoming a new version — and required it be settled by what each
does to the eight-week curve rather than by preference.

It is settled, and not by preference: **the schema already answered it.**
`0001_initial.sql` line 88 reads `version INTEGER NOT NULL, -- a prompt change
is a new version`, and `apps/api/secondshift/db/migrations/` is the authority on
the data model per `CLAUDE.md`. The rubric reached the same conclusion
independently: `config/evals/rubric.md` opens with "**Never edit in place** — a
changed rubric invalidates every prior score. Supersede with `rubric-v2.md`."

The eight-week argument the prompt asked for, written out. Someone edits the
researcher prompt on day 40:

- *If the version is manual*, invocations before and after both record
  `version = 1` against different `prompt_sha` values. The natural grouping key —
  `(name, version)` — silently merges two different prompts, so a week-1 to
  week-8 improvement attributed to the brain may be a prompt edit wearing the
  brain's credit. The sha can still tell them apart, but only for someone who
  thinks to look, and the curve reads as settled before anyone does.
- *If a changed file is a new version*, the grouping key separates them without
  anyone looking. The curve shows `v1 → v2` at day 40, and an improvement is
  attributable or it is visibly not.

Making the filename carry the version dissolves the remaining awkwardness:
there is no moment where the file on disk says `v1` while the row says `v2`,
because editing `researcher.v1.md` is refused rather than renamed. Registration
compares the file's content hash against the sha recorded for that version and
refuses on a mismatch, which is exactly the guard `reconcile-rubric-pinning`
added after an edit made only on the machine was destroyed by the next deploy.

**The prompts account for the model's visible reasoning by instructing it to
close, and by stripping the boundary the model itself emits.** Verified against
the live model on 2 Sep: the served checkpoint wraps its reasoning in
`<think>...</think>` inside `content`, no parser is configured, and a trivial
question spent 163 completion tokens almost entirely on deliberation. A prompt
written as though the model answers directly produces briefs opening with
"Here's a thinking process:".

Stripping is safe here and was not safe in `local-inference` — the distinction
matters. `VllmReasoner` deliberately does not split on a marker, because
guessing wrong there deletes the answer and corrupts token accounting. This
strips at the agent layer, on a delimiter the model emits structurally rather
than one inferred from prose, after telemetry has already counted the whole
completion. If the delimiter is absent the text passes through whole. Telemetry
still sees every token; only the rendered brief is trimmed.

**`max_tokens` is set knowing the model thinks inside the budget, not beside
it.** At 200 a one-sentence question returned reasoning and no answer at all.
The per-role budgets are configuration, in `config/models.toml`, not constants
in Python.

## Questions this change does not answer

**What the six prompts say.** Drafted, and marked in each file as a draft
awaiting the subject's judgment. The content is a question for the person being
assisted, and a draft treated as a decision would put words in their mouth for
the eight weeks the curve measures.
