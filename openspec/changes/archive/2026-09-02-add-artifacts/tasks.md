# Tasks — `artifacts`

## 1. The writer

- [x] 1.1 `secondshift/artifacts/store.py`: resolve the root, build the path from
      `night_of` / `run_id` / kind, write, read back, hash, insert.
- [x] 1.2 `content_sha` and `bytes` from the file as read back — never from the
      string that was passed in. A hash of the intent proves nothing about the
      write.
- [x] 1.3 A failed write raises before any row exists.
- [x] 1.4 `verify(artifact_row)` recomputing the hash, so a corrupted file is
      detectable rather than merely detectable in principle.
- [x] 1.5 Register `SECOND_SHIFT_ARTIFACTS` in `config.SETTINGS`. The enumeration
      test will fail until this is done — that is the point of it.

## 2. Variants

- [x] 2.1 `write_variants(...)`: one `variant_group`, enumerated
      `variant_index`, **no rank at insert time**.
- [x] 2.2 A variant that fails to generate does not stop the others, and the
      ones that landed keep their rows.
- [x] 2.3 `rank_group(...)`: apply a critic's ordering, all or nothing.
- [x] 2.4 Parse the ordering out of critic prose. Refuse a partial, repeated or
      unknown-index ordering without writing anything.

## 3. Outcomes

- [x] 3.1 `Repository.insert_outcome(...)`, honoring the CHECK that at least one
      of `label` / `signal` is present.
- [x] 3.2 Nothing infers an outcome. Assert it: a ranked group has no outcomes.
- [x] 3.3 `cost_per_accepted_artifact` returns a number once a `keep` exists,
      and excludes synthetic rows.

## 4. Wiring into the night

- [x] 4.1 Stages that produce something write it: `brief`, `research`
      (digest), `mockups`, `build`, `critique`, `distill` (summary).
- [x] 4.2 `build` and `mockups` write variants; the rest write single artifacts.
- [x] 4.3 The critique stage ranks the build group after it runs.
- [x] 4.4 **Nothing executes a generated build**, not even to check it parses.
- [x] 4.5 A write failure fails its stage without failing the run, per the
      blocking table `night-pipeline` already established.

## 5. Verification

- [x] 5.1 **Rank is not index**, asserted against the synthetic night whose ranks
      are a shuffled permutation. **Prove it can fail**: make the ranker write
      the index and watch it go red.
- [x] 5.2 Corrupt a written file; `verify` reports the mismatch.
- [x] 5.3 Two entries on one night do not collide.
- [x] 5.4 Partial fan-out: the survivors keep their rows and files.
- [x] 5.5 A `keep` makes the cost view return a number; synthetic rows excluded.
- [x] 5.6 No stored path contains an absolute location.
- [x] 5.7 Full suite, both guards, `openspec validate --strict`.

## 6. Not done here, recorded rather than dropped

- [x] 6.1 **The rank-trust question is unanswered.** It needs five real variants
      of a real brief, generated and read by the subject. The Spark has been
      unreachable since 2 Sep and `EchoReasoner` variants would make the
      comparison meaningless. Recommendation in the proposal: treat
      `variant_rank` as the critic's opinion and never let it select what an
      outcome defaults to.
- [x] 6.2 **No retention or deletion.** Tables are append-only; files are not.
      What "the artifact for this run" means after a cleanup is a decision, and
      guessing it here is worse than not having one.
- [x] 6.3 **No implicit `signal` outcomes.** Those need a UI that observes the
      person — `morning-interview` and the frontend. Only `label` ships.


## Mutations run, and the test one of them proved was missing

| Mutation | Result |
|---|---|
| The ranker writes `variant_index + 1` instead of the critic's position | `test_rank_is_never_the_generation_order` red |
| A partial ordering is applied instead of refused | all three `TestAPartialRankingIsRefused` assertions red |
| **`content_sha` hashes `content.encode()` rather than the file read back** | **stayed green** |

The third is the one worth having run. Hashing the intent instead of the file
left every test in `TestTheRecordDescribesWhatLanded` passing, because for a
successful write the two are byte-identical — which meant the design decision
this module argues for hardest had **no test behind it at all**. The corruption
tests do not cover it either: they damage the file after the row exists, so
`verify` catches them however the original hash was computed.

`test_a_short_write_is_recorded_as_what_landed` was added to close it: it patches
`Path.write_text` to truncate, and asserts the recorded hash matches the file on
disk and *differs* from the hash of what was passed in. Re-running the mutation
against it turns it red on the byte count. That is the only test here that
distinguishes "what landed" from "what was meant."

## Two defects found during implementation

- **`produced_by_invocation_id` was being given the agent id.** `AgentTurn`
  carried `agent_id` and not the invocation id, so the artifact pointed at the
  wrong table. The foreign key caught it rather than storing it. `AgentTurn` now
  carries `invocation_id`, which is what the requirement "every artifact names
  the invocation that produced it" actually needs.
- **`Stage.artifact_kind` is mapped explicitly, not by name.** Stage names and
  artifact kinds are separate CHECK constraints that overlap in five of six
  places — `research` produces a `research_digest`. Mapping by coincidence of
  name would have broken silently the first time either list moved.
  `assert_artifact_kinds_match_schema` reads the constraint.

## The rank-trust question is still open, and the run below is why

A night was run end to end. The structure is right and **the content is
worthless**, which is the honest result rather than a disappointing one:

```
2026-09-02/<run_a>/brief.md          2026-09-02/<run_b>/brief.md
2026-09-02/<run_a>/mockup/0/index.html   ...
2026-09-02/<run_a>/build/0/build.md
2026-09-02/<run_a>/critique.md
2026-09-02/<run_a>/summary.md
```

Two entries on one night, no collision — the layout decision holds. Every row
carries its invocation. Every `variant_rank` is NULL, and the ledger says why:

```
orchestrator_crash:night.critique.ranking |
  the critic's ordering [] does not cover exactly the variants in group '...'
```

That is the design working. The `cloud` profile binds `EchoReasoner`, whose
"critique" contains no ordering, so the ranker refused rather than filling the
column with the generation order. **The brief's content is the entry text echoed
back**, because the reasoner is a placeholder — a pipeline that produces
unreadable artifacts is a finding, and this is one. Nothing here can be said
about whether a real critic's ranking is trustworthy until the Spark returns.


## Corrected 2 Sep by a drift audit, after archiving

Four defects in what this change shipped. Left here rather than edited above,
because what was believed at archive time is part of the record.

- **`_variant_bodies`' docstring claimed the builder and architect prompts ask
  for a `## Variant N` heading. Neither does** — both end "Answer in plain
  prose". A fan-out therefore produces exactly one variant, and task 2.1's
  "one `variant_group`, enumerated `variant_index`" is true of a group of one.
  The machinery is correct; the input never exercises it.
- **Task 4.2 said "`build` and `mockups` write variants" and they do — as
  `.md`, not `.html`.** Mockups landed as `index.html` while the architect
  produces prose. Corrected.
- **`artifacts_for_run` was written for this change and never tested**, ordering
  included.
- **Nothing asserted the file extensions**, which is how the second was found:
  changing `.html` to `.md` broke no test.

Making the fan-out real needs a `v2` builder prompt, which is the subject's
call — a prompt change resets `prompt_sha` and that role's eight-week curve.
