---
name: "OpenSpec: Clarify"
description: Resolve [NEEDS CLARIFICATION] markers in OpenSpec changes via structured Q&A.
category: OpenSpec
tags: [openspec, clarify]
---

Resolve outstanding `[NEEDS CLARIFICATION: ...]` markers before implementation.

OpenSpec 1.11 has no native equivalent of this command. The rest of the enhanced
enforcement layer — scale classification, constitution gates, marker rules —
lives in `openspec/config.yaml` and applies to the native `/opsx:*` workflow.
This command is the piece with no native counterpart.

**Guardrails**
- Read `openspec/constitution.md` before resolving anything. An answer that
  violates a principle is not an acceptable resolution, however clearly the user
  states it — surface the conflict instead.
- Do not write implementation code. Only update marker text in `proposal.md` and
  `design.md`.
- Never resolve a marker by assumption. An unanswered question stays a marker.

**Step 1 — Find markers**

Run `openspec list` to identify active changes, then search
`openspec/changes/` for `[NEEDS CLARIFICATION:`. Report each as:

- file path and line number
- the question
- priority category: scope / security / UX / technical

If none are found, say so and stop — nothing needs doing.

**Step 2 — Resolve, in priority order**

Work strictly in order: scope, then security, then UX, then technical. Scope
questions can invalidate the answers to everything below them, so asking them
later wastes the user's time.

For each marker:

1. Put the question to the user with enough context to answer it. If there is a
   defensible default, recommend it and say why.
2. On a clear answer — replace the whole marker with the resolved text, written
   as a statement rather than a transcript of the exchange.
3. On "skip" — leave the marker in place. It will block `/opsx:apply`, which is
   correct.
4. On a partial answer — rewrite the marker to carry only the remaining
   ambiguity. Do not leave the original question standing when half of it is
   settled.

If an answer contradicts an accepted decision in `docs/decisions/`, say which
ADR and ask whether this supersedes it before writing the resolution.

**Step 3 — Summary**

Report markers found, resolved, and remaining. If all are resolved, say the
change is clear for `/opsx:apply`. If any remain, name them and say
implementation is blocked until they are answered.
