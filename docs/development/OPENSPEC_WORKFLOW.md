# OpenSpec Workflow

OpenSpec manages the lifecycle of project changes through structured proposals, implementation, and archival.

## Lifecycle

```
Request → Scale Classification → Constitution Check → Proposal → Clarify → Apply → Archive
```

### 1. Scale Classification

Every request is classified before any work begins:

| Level | Name | Triggers | Required Artifacts |
|-------|------|----------|-------------------|
| 0 | Bug Fix | Restores intended behavior | None — fix directly |
| 1 | Small Task | <1 day, single component | `tasks.md` only |
| 2 | Feature | Standard change | `proposal.md` + `tasks.md` |
| 3 | Epic | Cross-system, multi-week | `proposal.md` + `design.md` + `tasks.md` |
| 4 | Enterprise | Architectural shift | All L3 + cost section + `artifacts/` dir |

Level 0 requests bypass the proposal workflow entirely.

### 2. Constitution Check

Before creating a proposal, the AI reads `openspec/constitution.md` and checks for violations. Constitution violations are **CRITICAL BLOCKING FINDINGS** -- the proposal cannot proceed.

### 3. Proposal (`/openspec:proposal`)

Creates a structured proposal with:
- Scale level classification
- Constitution compliance confirmation
- Clarification markers for ambiguous requirements

### 4. Clarify (`/openspec:clarify`)

Resolves `[NEEDS CLARIFICATION: ...]` markers through structured Q&A. Markers are prioritized: scope > security > UX > technical.

Rules:
- Max 3 markers per spec file
- Markers go in `proposal.md` or `design.md`, never in `tasks.md`
- All markers must be resolved before implementation

### 5. Apply (`/openspec:apply`)

Implements the proposal after two pre-flight checks:
1. No unresolved clarification markers
2. Constitution compliance verified

### 6. Archive (`/openspec:archive`)

Archives completed proposals. Warns if unresolved markers exist.

## Directory Structure

```
openspec/
├── AGENTS.md              # Auto-generated agent instructions
├── constitution.md        # Immutable project principles
├── project.md             # Project context
└── proposals/
    └── <proposal-name>/
        ├── proposal.md    # Problem, scope, approach
        ├── design.md      # Technical design (L3+)
        ├── tasks.md       # Implementation tasks
        └── artifacts/     # Supporting docs (L4)
```

## Commands

| Command | Description |
|---------|-------------|
| `/openspec:proposal <description>` | Create a new proposal |
| `/openspec:clarify` | Resolve clarification markers |
| `/openspec:apply` | Implement the proposal |
| `/openspec:archive` | Archive a completed proposal |

## Constitution

The constitution (`openspec/constitution.md`) defines immutable principles that all proposals must comply with. Common principles include:

- Multi-tenant isolation
- Parameterized queries only
- Authentication on all endpoints
- Secrets encrypted at rest
- Test coverage requirements
- API backward compatibility

Add project-specific principles below the marker line in `constitution.md`.

## Clarification Markers

Format: `[NEEDS CLARIFICATION: <specific question>]`

These markers flag ambiguous requirements for explicit resolution before implementation begins. They prevent assumptions from propagating into code.
