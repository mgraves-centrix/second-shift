# Agents prompt

Paste as the first message of a fresh session. Local, plus one optional read
against the Spark's reasoner if you have tailnet access.

---

Build `agents`. Read `openspec/constitution.md`, `CLAUDE.md`, and
`docs/SPEC_ROADMAP.md` first; they are the rules, not background.

## Why this one

**Nothing in this system reasons in production, and the reason is not the model.**
`local-inference` shipped, the registry binds a real `Reasoner`, and
`nemotron-3.5-lightning` has been serving on the Spark for days. Nothing calls
it, because there is no agent to do the calling.

`night-pipeline` cannot start without this. `morning-interview` cannot either.
It is the narrowest thing standing between a working model and a working product.

There is also a measurement problem hiding here. `agents.prompt_sha` is
`NOT NULL` and exists so that an improving eight-week curve can be shown to
measure the brain rather than a quietly edited prompt. The only thing writing
that column today is a test fixture writing the literal `deadbeef`, against a
path — `agents/prompts/researcher.v1.md` — that has never existed. That is the
same class of defect as the rubric hash, in a second place, and it becomes
permanent the moment a real invocation records it.

## What already exists — do not invent any of it

- `docs/ARCHITECTURE.md` specifies `agents/ roster + versioned prompt files`.
  **The directory does not exist.** This builds it.
- The `agents` table: `name`, `role`, `version`, `prompt_path`, `prompt_sha`,
  `default_model_local`, `default_model_cloud`, `created_at_ms`, `retired_at_ms`,
  `UNIQUE(name, version)`.
- `role` is a six-value CHECK and the set is fixed: `interviewer`, `researcher`,
  `architect`, `builder`, `critic`, `distiller`. Do not add a seventh.
- `Repository.insert_agent(...)` exists and takes `prompt_path` and `prompt_sha`.
- `Recorder.invocation(agent_id, run_id=, stage=)` opens and closes the
  invocation row, with parentage and depth from the surrounding context.
- The `Reasoner` interface is `complete(messages, policy=, effort=)`. The base
  class owns telemetry; you write none.
- `docs/MODELS.md` binds the models per profile, and the escalation policy is
  already written there: `local-only` never escalates; `cloud-assisted` uses
  Lightning for routine turns, Super for research synthesis, architect and
  critic, Ultra only when Super's critique is rejected twice.

**Verified against the live model on 2 Sep, and it shapes every prompt you
write:** the served checkpoint emits its reasoning inline, wrapped in
`<think>...</think>`, inside `content`. No reasoning parser is configured, so
`usage` carries no split and the whole thing lands in `completion_tokens`. A
trivial question — "Reply with exactly: OK" — spent 163 completion tokens, nearly
all of it deliberation. At `max_tokens=200` a one-sentence question returned
reasoning and no answer at all.

## The open decision

**Two, and they are different in kind.**

**What the prompts say is not yours.** Like the brain's topic files, the content
is a question for the subject. Draft each prompt, mark it explicitly as a draft
in the file, and do not treat your draft as the decision.

**How a prompt version bumps is yours, and must not be decided by preference.**
Either `version` is manual and `prompt_sha` merely records what was used, or a
changed file is automatically a new version. Decide it by writing down what each
choice does to the eight-week curve when a prompt is edited on day 40 — one of
them makes the curve interpretable and one makes it a footnote. Put that
reasoning in the proposal.

## What good looks like

- Six prompt files on disk, versioned in their filename, one per role.
- `prompt_sha` is **computed from the file content** at registration. Never
  passed in, never defaulted, never `deadbeef`.
- Registering an agent whose prompt file is missing **fails loudly**. A roster
  row pointing at a file that is not there is worse than no row.
- An agent invocation opens a telemetry row with the right parentage, calls the
  bound `Reasoner`, and records the model call — all of it through the existing
  machinery, none of it reimplemented.
- The prompts account for the visible chain-of-thought. Whatever you choose —
  instruct the model to close its thinking, strip on the boundary the model
  itself emits, or leave it whole and make the renderer's problem explicit —
  **say which, and why, in the proposal.** A prompt written as though the model
  answers directly will produce briefs that open with "Here's a thinking
  process:".
- `max_tokens` is set knowing the model thinks inside that budget, not beside it.

## Scope — what NOT to build

- **No night pipeline.** Agents are invocable; what invokes them in sequence is
  `NIGHT_PIPELINE.md`.
- **No retrieval.** An agent takes the context it is handed.
- **No new roles.** Six, fixed by a database CHECK.
- **No agent framework.** No graph, no router, no tool-calling loop. A role, a
  prompt, a model binding, an invocation.
- Do not put model identifiers in `.py` — they live in `config/models.toml`.

## Constitution hooks

- **Principle 7 governs.** Every invocation opens an `agent_invocations` row and
  every model call writes `model_calls`, from the first run. The base classes
  already guarantee it; your job is not to route around them.
- **Principle 2.** An agent runs under a policy and passes it explicitly to
  `complete()`. It never reads a policy from context and never defaults one.
  A `local-only` invocation that reaches a remote provider fails at the call and
  again at the database — do not add a path that tries.
- **Principle 5.** Provider specifics stay in `providers/`. An agent knows
  `Reasoner`, not vLLM.
- **Principle 1.** Agent prompts are versioned text under git, for the same
  reason the brain is. Do not move them into the database.

## The loop

```bash
git status --short && openspec list && openspec list --specs
apps/api/.venv/bin/python -m pytest apps/api/tests -q          # 302 pass today
npm --prefix apps/web run test && npm --prefix apps/web run typecheck
scripts/check-no-environment.sh && scripts/check-american-english.sh
```

All green before starting. Then propose, clarify, apply, verify, sync, archive.

## Verification — the sha is the load-bearing part

- **`prompt_sha` equals the sha256 of the file it names.** Assert it for every
  registered agent, against the real files. Then edit a prompt file in the test
  and assert the recorded sha changes. **Prove it can fail:** hardcode the sha to
  a constant and watch the suite go red. If it stays green, the pinning is
  decorative and you have rebuilt `deadbeef` with extra steps.
- Registering against a missing prompt file raises, and writes no row.
- An invocation records its row with the expected parent and depth.
- A `local-only` invocation against a remote provider is refused at the call.
- The six roles round-trip: every role in the CHECK has exactly one registered
  agent, and the test enumerates the CHECK rather than a hand-written list.
- Exercise an agent against a **stub** `Reasoner`, not the live model, so the
  suite stays hermetic. If you have tailnet access, additionally make one real
  call and paste what came back — but never make the suite depend on it.

## Quality bar

The code is the submission. Judges read this repository.

**Never ship:** a `TODO`; a prompt file that is a placeholder; a `prompt_sha`
that is anything but a hash of the file; a test that passes with the
implementation deleted; a mock of the thing under test; an agent that writes its
own telemetry.

**Always:** match the surrounding idiom; write the test that would have caught
the bug; keep provider specifics inside `providers/`; keep writes inside the
recorder's lock; let failures be loud. American English. No hostnames,
addresses, usernames or home paths in tracked files.

## Hard stops

Stop, record the question with your recommendation, and move on:

- A `[NEEDS CLARIFICATION]` marker. Do not answer your own — and the *content*
  of the prompts is exactly the kind of thing you must not decide for the
  subject.
- A constitution violation. Blocking, not advisory.
- Anything in `NOT_BUILDING.md`.
- Credentials, payment, account settings, or anything outward-facing.
- Rewriting published history or force-pushing.

## Report

1. The versioning decision, with the eight-week argument that settled it.
2. What you did about the visible chain-of-thought, and what a brief looks like
   as a result — paste one. **If it still opens with "Here's a thinking
   process:", say so**; that is the finding, not a detail to fix later.
3. What shipped, with test counts.
4. The six prompts, flagged plainly as drafts awaiting the subject's judgment.
5. Anything blocked, with your recommendation.
6. What you would do next, and why that rather than the alternative.
