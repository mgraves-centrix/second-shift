# Check the drift on every commit, instead of whenever somebody looks

## Scale classification

**L1 — Small task.** One script, one gate row, one marker convention. No schema
change, no behavior change, nothing a user of the product sees.

## Why

`docs/SPEC_ROADMAP.md` carries a section called "The drift pass — 2 Sep" with
twelve findings in a table, every one of them a claim in a document that had
stopped being true. It was done by hand. It has been done by hand several times
since, and each pass found more.

**The passes work. The problem is that they are passes.** A check that runs when
somebody remembers to look is a check whose coverage is the memory of whoever is
looking, and the evidence for that is in this repository's own history: the
`ARCHITECTURE.md` tree was "wrong for a week because nobody did" — its own words,
in the paragraph above the tree.

Two claims were wrong before this proposal was written, found by spot-checking
for thirty seconds:

| Claim | Where | Reality |
|---|---|---|
| `app.py` "is 79 lines" | `docs/prompts/00_INDEX.md:73` | 80 |
| `night/` and `morning/` marked `(planned)` | `docs/ARCHITECTURE.md` | Both shipped, 2 and 3 Sep |

The first is two days old and I wrote it. The second is the same tree that was
corrected on 16 Sep for asserting directories that did not exist — the pass
fixed one direction and left the other.

## What changes

**`scripts/check-drift.py`**, and a row in `scripts/gate.py`. Three checks, each
chosen because this project has a recorded instance of the thing it catches, and
each with no prose parsing in it — a checker that guesses produces false
positives, and a checker with false positives is one people learn to ignore.

### 1. The documented tree is the real tree

Every path in `ARCHITECTURE.md`'s directory block exists, **and** every path
marked `(planned)` does not. Both directions: a tree that asserts what is absent
misleads a reader about what was built, and a tree that calls shipped work
planned misleads them about what is left.

### 2. A derived number matches what it derives from

Prose carries the derivation inline:

```markdown
it is 80 lines <!-- derived: lines apps/api/secondshift/api/app.py -->
```

The checker finds the markers, recomputes, and compares. **Zero false positives
by construction**, because nothing is inferred from prose — a number is checked
only if somebody said what it means, and an unmarked number is exactly as
unchecked as it is today.

Derivations: `lines <path>`, `count <glob>`. Both are what the stale claims in
this repository have actually been.

### 3. The bookkeeping says what is true

- An active change whose `tasks.md` has no unchecked box reads as finished in
  `openspec list`. `nebius-executor` read **"✓ Complete"** for three weeks with
  none of the work done, because its second task group was three sentences of
  prose rather than tasks.
- A canonical spec with no archived change that created it means a sync happened
  without an archive, which leaves a requirement in force whose proposal is
  still open.

Both hold today. They are guards rather than repairs.

## What this does not do

**It does not check semantics.** The sharpest drift this session was a proposal
promising a route that its own design, ninety lines below, had decided against.
No script finds that, and pretending otherwise would be the worse failure: a
green drift gate that a reader takes as "the documents agree".

The script says so in its own header, because a tool that overstates its
coverage is how the passes stop happening.

## Impact

**Affected specs:** `test-harness` (one added requirement).

**Affected code:** `scripts/check-drift.py` (new), `scripts/gate.py`,
`docs/development/GATES.md`. Markers added to the handful of derived numbers
that exist today, and `ARCHITECTURE.md` corrected.

## Constitution Compliance

| Principle | Bearing | How this change stands |
|---|---|---|
| 1. Brain plaintext under git | Not engaged | Reads this repository only. |
| 2. The Privacy Airlock | Not engaged | No content leaves; it reads tracked files and counts them. |
| 3. No empty mornings | Not engaged | — |
| 4. Text-first, voice layered | Not engaged | — |
| 5. One codebase, two deployments | Not engaged | A development gate. Nothing ships it. |
| 6. Scope boundary | Respected | Not a product surface. |
| 7. Telemetry from line one | **Considered, deliberately not applied** | No model call, no invocation. It is a check somebody runs, and the gate's own output is its record. |

No violation.

## Risk

**A checker that cries wolf gets suppressed.** Which is why nothing is inferred
from prose and every check was run against this repository before being
proposed: two found something, one holds and is a guard.

**A green gate read as "the documents are true."** Mitigated by saying, in the
script's own output and in `GATES.md`, exactly which three things it checked.
