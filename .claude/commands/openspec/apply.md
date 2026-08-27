---
name: OpenSpec: Apply
description: Implement an approved OpenSpec change with pre-flight marker check and constitution compliance.
category: OpenSpec
tags: [openspec, apply]
---
<!-- OPENSPEC:START -->
**Guardrails**
- Favor straightforward, minimal implementations first and add complexity only when it is requested or clearly required.
- Keep changes tightly scoped to the requested outcome.
- Refer to `openspec/AGENTS.md` (located inside the `openspec/` directory—run `ls openspec` or `openspec update` if you don't see it) if you need additional OpenSpec conventions or clarifications.

**Pre-Flight Check 1 — Clarification Markers**

Search all files in the active change directory (`openspec/changes/<id>/`) for `[NEEDS CLARIFICATION:`. If ANY markers are found:
1. List each marker with its file and line
2. **BLOCK implementation** — do not proceed
3. Instruct the user to run `/openspec:clarify` first

**Pre-Flight Check 2 — Constitution Compliance**

Read `openspec/constitution.md`. Review the change proposal against each principle. If any violation is found:
1. Report the violation as a **CRITICAL BLOCKING FINDING**
2. **BLOCK implementation** — do not proceed
3. Explain what needs to change for compliance

**Steps**

Track these steps as TODOs and complete them one by one.
1. Read `changes/<id>/proposal.md`, `design.md` (if present), and `tasks.md` to confirm scope and acceptance criteria.
2. Work through tasks sequentially, keeping edits minimal and focused on the requested change.
3. After each task, verify constitution compliance is maintained.
4. Confirm completion before updating statuses — make sure every item in `tasks.md` is finished.
5. Update the checklist after all work is done so each task is marked `- [x]` and reflects reality.
6. Reference `openspec list` or `openspec show <item>` when additional context is required.

**Reference**
- Use `openspec show <id> --json --deltas-only` if you need additional context from the proposal while implementing.
<!-- OPENSPEC:END -->
