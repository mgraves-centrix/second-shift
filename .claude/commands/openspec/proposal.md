---
name: OpenSpec: Proposal
description: Scaffold a new OpenSpec change with scale classification, constitution enforcement, and clarification markers.
category: OpenSpec
tags: [openspec, change, proposal]
---
<!-- OPENSPEC:START -->
**Guardrails**
- Favor straightforward, minimal implementations first and add complexity only when it is requested or clearly required.
- Keep changes tightly scoped to the requested outcome.
- Refer to `openspec/AGENTS.md` (located inside the `openspec/` directory—run `ls openspec` or `openspec update` if you don't see it) if you need additional OpenSpec conventions or clarifications.
- Identify any vague or ambiguous details and ask the necessary follow-up questions before editing files.
- Do not write any code during the proposal stage. Only create design documents (proposal.md, tasks.md, design.md, and spec deltas). Implementation happens in the apply stage after approval.

**Step 0 — Scale Classification**

Before anything else, classify the request:

| Level | Name | Triggers | Required Artifacts |
|-------|------|----------|-------------------|
| 0 | Bug Fix | Restores intended behavior | None — fix directly, skip this proposal flow |
| 1 | Small Task | <1 day, single component | `tasks.md` only |
| 2 | Feature | Standard change | `proposal.md` + `tasks.md` |
| 3 | Epic | Cross-system, multi-week | `proposal.md` + `design.md` + `tasks.md` |
| 4 | Enterprise | Architectural shift, audit required | All L3 + cost section + `artifacts/` dir |

State the level and rationale. If Level 0, stop here — fix the bug directly without a proposal.

**Step 1 — Constitution Check**

Read `openspec/constitution.md`. For each principle, evaluate whether the proposed change could violate it. If ANY violation is found, report it as a **CRITICAL BLOCKING FINDING** — the proposal cannot proceed until resolved or explicitly overridden by the user.

**Step 2 — Scaffold Proposal**

1. Review `openspec/project.md`, run `openspec list` and `openspec list --specs`, and inspect related code or docs (e.g., via `rg`/`ls`) to ground the proposal in current behaviour; note any gaps that require clarification.
2. Choose a unique verb-led `change-id` and scaffold `proposal.md`, `tasks.md`, and `design.md` (when needed) under `openspec/changes/<id>/`.
3. Map the change into concrete capabilities or requirements, breaking multi-scope efforts into distinct spec deltas with clear relationships and sequencing.
4. Capture architectural reasoning in `design.md` when the solution spans multiple systems, introduces new patterns, or demands trade-off discussion before committing to specs.
5. Draft spec deltas in `changes/<id>/specs/<capability>/spec.md` (one folder per capability) using `## ADDED|MODIFIED|REMOVED Requirements` with at least one `#### Scenario:` per requirement and cross-reference related capabilities when relevant.
6. Draft `tasks.md` as an ordered list of small, verifiable work items that deliver user-visible progress, include validation (tests, tooling), and highlight dependencies or parallelizable work.

**Step 3 — Enhance with Clarification Markers**

Where requirements are ambiguous, insert markers: `[NEEDS CLARIFICATION: <specific question>]`
- Max 3 markers per file
- Priority: scope > security > UX > technical
- Place in `proposal.md` or `design.md`, never in `tasks.md`

Add a "Constitution Compliance" section in `proposal.md` confirming no violations found.

**Step 4 — Validate**

Run `openspec validate <id> --strict` and resolve every issue before presenting the proposal.

**Step 5 — Summary**

Present:
- Scale level and rationale
- Constitution compliance status
- Any clarification markers that need resolution (suggest running `/openspec:clarify`)
- Next steps based on scale level

**Reference**
- Use `openspec show <id> --json --deltas-only` or `openspec show <spec> --type spec` to inspect details when validation fails.
- Search existing requirements with `rg -n "Requirement:|Scenario:" openspec/specs` before writing new ones.
- Explore the codebase with `rg <keyword>`, `ls`, or direct file reads so proposals align with current implementation realities.
<!-- OPENSPEC:END -->
