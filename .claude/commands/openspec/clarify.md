---
name: OpenSpec: Clarify
description: Resolve [NEEDS CLARIFICATION] markers in OpenSpec changes via structured Q&A.
category: OpenSpec
tags: [openspec, clarify]
---
<!-- OPENSPEC:START -->
**Guardrails**
- Refer to `openspec/AGENTS.md` if you need additional OpenSpec conventions or clarifications.
- Do not write any code during clarification. Only update the marker text in proposal/design documents.

**Step 1 — Find Markers**

Search all files in `openspec/changes/` for `[NEEDS CLARIFICATION:` markers. Run `openspec list` to identify active changes. List each marker with:
- File path and line number
- The specific question in the marker
- Priority category (scope / security / UX / technical)

If no markers found, report that all clarifications are resolved and no action is needed.

**Step 2 — Resolve Each Marker**

For each marker, in priority order (scope > security > UX > technical):
1. Present the question to the user
2. If the user provides an answer, replace the `[NEEDS CLARIFICATION: ...]` marker with the resolved text
3. If the user says "skip", leave the marker in place
4. If the user provides a partial answer, update the marker to reflect remaining ambiguity

**Step 3 — Summary**

Report:
- Total markers found
- Markers resolved
- Markers remaining
- If all resolved, suggest running `/openspec:apply` to proceed with implementation
<!-- OPENSPEC:END -->
