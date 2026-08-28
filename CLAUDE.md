# Second Shift

An always-on assistant that turns half-formed ideas into artifacts overnight,
then interviews you in the morning about what it got stuck on.

## Read first

| Document | What it settles |
|---|---|
| `openspec/constitution.md` | Immutable principles. Violations block work. |
| `NOT_BUILDING.md` | Deliberately excluded features and the override protocol. |
| `docs/ARCHITECTURE.md` | Compute profiles, the Nebius split, the Privacy Airlock. |
| `docs/DATA_MODEL.md` | Schema decisions and why they are what they are. |
| `docs/decisions/` | Numbered ADRs. Read before proposing architecture. |
| `docs/MODELS.md` | Exact model bindings per compute profile. |

`apps/api/secondshift/db/migrations/` is the authority on the data model;
`0001_initial.sql` is the base schema.

## Conventions

- Work from the repository root. Pass absolute paths. Never `cd`.
- Never run `uv run` on the DGX Spark — it re-resolves the environment to
  x86_64 and destroys it. Use `python -m venv` + `pip` with pinned constraints.
- Time is `INTEGER` epoch milliseconds UTC everywhere. Local framing lives on
  `entries.captured_tz` / `tz_offset_min`.
- Tables are append-only. Counters are views, never stored columns.
- Every agent invocation and model call writes telemetry, including during
  development. Instrumentation is part of the task, never a follow-up.
- **This repository is public.** No hostnames, tailnet names, private addresses,
  usernames or home paths in tracked files — use placeholders and environment
  variables. `scripts/check-no-environment.sh` enforces it.

<!-- OPENSPEC:START -->
## OpenSpec

This project uses OpenSpec 1.11 (`@fission-ai/openspec`) for spec-driven
development, with an enforcement layer ported from
`centrix-labs/enhanced-openspec`.

**Workflow — use the native commands:**

| Command | Purpose |
|---|---|
| `/opsx:explore` | Think through an idea before proposing |
| `/opsx:propose` | Create a change with all artifacts |
| `/openspec:clarify` | Resolve `[NEEDS CLARIFICATION]` markers |
| `/opsx:apply` | Implement an approved change |
| `/opsx:archive` | Archive a completed change |

**Enforcement** lives in `openspec/config.yaml` — scale classification (L0–L4),
constitution checks, clarification-marker rules, and apply/archive pre-flight
gates. It applies automatically to the native workflow; there is no separate
command namespace to remember.

`/openspec:clarify` is the one enhanced command retained, because OpenSpec 1.11
has no native equivalent.

See `docs/development/OPENSPEC_WORKFLOW.md` for the full lifecycle.
<!-- OPENSPEC:END -->
