## Scale

**L2 — Feature.** One capability's contract: what retrieval indexes, and where
a document's policy comes from. No design doc — the policy question is settled
by provenance rather than by preference, and the reasoning is below.

## Why

The eval rubric's second dimension, "did it use what it knows about me", is the
one that measures learning. Level 3 is using the profile or style guide; level 4
is using something learned from a prior decision or outcome.

Neither was reachable. Brain topic files carry `local-only` (ADR 0010), so a
`cloud-assisted` run — which is every real entry captured so far — never sees
them. Decisions and outcomes were not indexed at all, and neither was what the
distiller writes to `nights/`: the night wrote down what it learned every night
and nothing ever read it.

An eight-week curve over that measures a brain that could not have been used.

## What Changes

Three sources become retrievable memory, each carrying the policy of the work
behind it rather than a blanket one:

- **Night distillations.** One run produced each file, and its name carries that
  run's id, so its policy is the stricter of the run's own and its entry's — a
  `local-only` entry widened by a decision still worked on private material. A
  file whose run cannot be resolved is `local-only`.
- **Answered decisions**, under their entry's policy. An unanswered question is
  not memory; it records what could not be decided.
- **Outcomes**, under their entry's policy.

Not in this change: revising `profile.md` and `style-guide.md`, which is the
distiller's v2 prompt and the visible half of ADR 0007's argument. It is next,
and it is a prompt decision rather than a code one.

## Why this does not weaken ADR 0010

ADR 0010 gives brain topic files `local-only` because they are distilled across
every entry with no way to tell which sentence came from where. That reasoning
is about provenance, not about the brain as a place. A night file, a decision
and an outcome each belong to exactly one entry whose policy is recorded, so the
policy here is read rather than assumed, and the stricter of the two available
values is the one used. Nothing distilled across mixed material changes status,
and `assemble_context` is unchanged.

## Constitution Compliance

| Principle | Status | Note |
|---|---|---|
| 1. Brain plaintext under git | **Implements** | What the night learned is markdown under git, and is now read back as memory rather than only written. |
| 2. Privacy Airlock | **Constrains** | Every new document carries a policy derived from its own origin, strictest-wins, `local-only` where the origin cannot be resolved. The assembly filter is untouched. |
| 3. No empty mornings | Not applicable | |
| 4. Text-first | Not applicable | |
| 5. One codebase, two deployments | Compliant | The judge instance indexes its seeded corpus the same way. |
| 6. Scope boundary | Compliant | Memory in between, which is the boundary's own middle term. |
| 7. Telemetry from line one | Not applicable | No new model call. |

No violations.
