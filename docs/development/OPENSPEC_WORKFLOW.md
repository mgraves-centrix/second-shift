# OpenSpec Workflow

Second Shift uses [OpenSpec](https://github.com/Fission-AI/OpenSpec) 1.11 for
spec-driven development, with an enforcement layer ported from
[`centrix-labs/enhanced-openspec`](https://github.com/centrix-labs/enhanced-openspec).

## Why this is a port and not an install

`enhanced-openspec` targets OpenSpec 0.18, which drove everything through a
generated `openspec/AGENTS.md` and a set of `/openspec:*` commands. OpenSpec
1.11 replaced that architecture with skills, a native `/opsx:*` command set, and
`openspec/config.yaml`. It no longer generates `AGENTS.md` at all, and it treats
`project.md` as legacy.

Run verbatim against 1.11, the enhanced commands reference a file that will
never exist. So the enforcement was ported into 1.11's own extension points
rather than layered beside them:

| Enhanced feature (0.18) | Where it lives now |
|---|---|
| Scale classification L0–L4 | `config.yaml` → `rules.proposal` |
| Constitution check at proposal | `config.yaml` → `rules.proposal` |
| Constitution re-check at apply | `config.yaml` → `operations.apply.guidance` |
| Clarification-marker rules | `config.yaml` → `rules.proposal` / `rules.design` |
| Markers forbidden in tasks | `config.yaml` → `rules.tasks` |
| Marker pre-flight block on apply | `config.yaml` → `operations.apply.guidance` |
| Unresolved-marker warning on archive | `config.yaml` → `operations.archive.guidance` |
| `/openspec:clarify` | Retained as a command — 1.11 has no equivalent |
| `openspec/constitution.md` | Unchanged — 1.11 has no constitution concept |

One workflow instead of two, and it stays on upstream rails as OpenSpec keeps
moving.

**On "hard gates":** enhanced-openspec describes these as blocks the AI cannot
bypass. In both 0.18 and here they are prompt-level instructions, not mechanical
enforcement. The one genuinely mechanical gate in this project is the Privacy
Airlock, which is a `CHECK` constraint in `schema.sql` — the database refuses
the write.

## Lifecycle

```
idea
  │
  ▼
/opsx:explore ............ optional; think before proposing
  │
  ▼
scale classification ..... L0? fix directly, no proposal
  │
  ▼
constitution check ....... violation → BLOCKED
  │
  ▼
/opsx:propose ............ proposal.md, specs/, design.md (L3+), tasks.md
  │                        ambiguity → [NEEDS CLARIFICATION: ...]
  ▼
/openspec:clarify ........ resolve markers, scope → security → UX → technical
  │
  ▼
markers remaining? ....... yes → BLOCKED
  │
  ▼
you review and approve
  │
  ▼
/opsx:apply .............. re-checks constitution, implements tasks in order
  │
  ▼
/opsx:archive ............ merges deltas into openspec/specs/
```

## Scale levels

| Level | Name | Artifacts | When |
|---|---|---|---|
| 0 | Bug Fix | none — fix directly | Broken behavior, clear fix |
| 1 | Small Task | `tasks.md` | Under a day, single component |
| 2 | Feature | `proposal.md` + `tasks.md` | New user-facing functionality |
| 3 | Epic | + `design.md` | Cross-system, multi-week |
| 4 | Enterprise | + cost section, `artifacts/` | Architectural shift |

## Clarification markers

`[NEEDS CLARIFICATION: <specific question>]`

- Maximum 3 per file
- `proposal.md` and `design.md` only — never `tasks.md`
- Priority: scope → security → UX → technical
- Unresolved markers block `/opsx:apply`

Scope questions can invalidate the answers below them, which is why they are
asked first.

## Directory layout

```
openspec/
├── config.yaml        schema, project context, rules, operation guidance
├── constitution.md    immutable principles — violations are blocking
├── specs/             canonical specs — what IS built
└── changes/           active proposals — what SHOULD change
    ├── <change-id>/
    │   ├── proposal.md
    │   ├── design.md      L3+
    │   ├── tasks.md
    │   └── specs/         deltas: ADDED / MODIFIED / REMOVED
    └── archive/
```

## Commands

| Command | Purpose |
|---|---|
| `/opsx:explore` | Think through an idea before proposing |
| `/opsx:propose` | Create a change with all artifacts |
| `/opsx:update` | Revise an existing change's artifacts |
| `/openspec:clarify` | Resolve `[NEEDS CLARIFICATION]` markers |
| `/opsx:apply` | Implement an approved change |
| `/opsx:sync` | Sync deltas into main specs without archiving |
| `/opsx:archive` | Archive a completed change |

CLI: `openspec list`, `openspec list --specs`, `openspec show <id>`,
`openspec validate <id> --strict`, `openspec doctor`, `openspec status`.

## Maintenance

The CLI is installed globally at a pinned version. To move it:

```bash
npm install -g @fission-ai/openspec@<version> && openspec update --force
```

Check `openspec templates` and `openspec schemas` after any major version bump —
artifact names feed `config.yaml`'s `rules` keys, and a rename would silently
disable a rule.
