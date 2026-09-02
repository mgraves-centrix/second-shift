# Design — `artifacts`

## Context

The schema has carried `variant_group`, `variant_index` and `variant_rank` since
`0001_initial.sql` with nothing writing them, and `insert_artifact` exists
because the seed generator needed it. So the storage shape is settled. What is
open is who writes it, what lands on disk, and how a rank gets there without
being the generation order in disguise.

## Decision 1 — bytes first, then the row

The writer writes the file, then hashes **what it read back from disk**, then
inserts the row.

```
write → read back → sha256 + len → insert
```

**Alternative considered:** hash the string in memory and write both. Rejected —
that hash proves what was intended, not what landed. A truncated write, a full
disk, or an encoding surprise all produce a row whose `content_sha` is confidently
wrong, and the whole point of the column is detecting exactly that. Reading back
costs one syscall on a file the page cache already holds.

**Consequence:** a failed write raises before any row exists. There is no
artifact row pointing at a file that is not there, which is the same rule
`agents.roster` applies to prompt files and for the same reason.

## Decision 2 — the three variant fields are computed in three different places

They are conflated by accident, not by intent, so they are kept apart by
construction:

| Field | Written by | From |
|---|---|---|
| `variant_group` | the writer, once per fan-out | a fresh ULID for the group |
| `variant_index` | the writer, per variant | enumeration order of generation |
| `variant_rank` | **the ranker, afterward** | the critic's ordering, parsed from its output |

`variant_rank` is never written at insert time. The writer physically cannot set
it to the index because it does not have a rank to write yet — the rank is a
separate update after the critic has spoken.

**Alternative considered:** write rank at insert, defaulting to index, and update
later. Rejected — the default *is* the bug. A run whose critic failed would carry
a full set of plausible ranks that are really the generation order, and nothing
downstream could tell them from real ones. NULL is the honest value for "not
ranked", and `cost_per_accepted_artifact` does not read rank at all, so NULL
costs nothing.

## Decision 3 — ranking parses an ordering, and refuses a partial one

The critic returns prose. The ranker extracts an ordering of variant indices from
it and applies it. Where the ordering does not cover exactly the variants in the
group — a repeat, a missing one, an index that does not exist — **nothing is
written**.

**Alternative considered:** apply what parsed and leave the rest NULL. Rejected —
a group with three of five ranked reads as a complete ranking to anything that
sorts by rank and puts NULLs last. All or nothing keeps "ranked" a property of
the group rather than of individual rows.

This is the seam `nebius-executor` substitutes at: the ranker takes a list of
variants and returns an ordering, and it does not care whether they were produced
in a loop here or by five parallel Jobs.

## Decision 4 — outcomes are recorded, never inferred

`insert_outcome` writes what it is told. Nothing derives an outcome from a rank,
from an artifact being opened, or from a run completing.

The `signal` column exists for implicit outcomes (`opened`, `iterated`, `used`,
`exported`, `ignored`) and this capability writes none of them — that needs a UI
that observes the person, which is `morning-interview`'s and the frontend's
territory. What ships is the recording path and `label`, the explicit judgement.

**Why this matters more than it looks:** `cost_per_accepted_artifact` counts
`label = 'keep'`. If anything in this capability inferred a `keep` — from a rank,
say — the submission's headline chart would be measuring the critic agreeing with
itself. The chart is only worth showing because a person put the `keep` there.

## Decision 5 — the root is configuration, the stored path is relative

`SECOND_SHIFT_ARTIFACTS`, defaulting beside the database. `artifacts.path` holds
the path relative to that root.

**Alternative considered:** store absolute paths. Rejected twice over — the judge
instance has a different root, so absolute paths would need rewriting at deploy;
and an absolute path pins a home directory into rows a judge reads, which
`scripts/check-no-environment.sh` exists because of.

Adding this variable makes `configuration`'s enumeration test fail until it is
registered. That is the test working: it was written on the argument that the
count had already drifted by three without anyone noticing.
