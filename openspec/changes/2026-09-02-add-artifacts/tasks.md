# Tasks — `artifacts`

## 1. The writer

- [ ] 1.1 `secondshift/artifacts/store.py`: resolve the root, build the path from
      `night_of` / `run_id` / kind, write, read back, hash, insert.
- [ ] 1.2 `content_sha` and `bytes` from the file as read back — never from the
      string that was passed in. A hash of the intent proves nothing about the
      write.
- [ ] 1.3 A failed write raises before any row exists.
- [ ] 1.4 `verify(artifact_row)` recomputing the hash, so a corrupted file is
      detectable rather than merely detectable in principle.
- [ ] 1.5 Register `SECOND_SHIFT_ARTIFACTS` in `config.SETTINGS`. The enumeration
      test will fail until this is done — that is the point of it.

## 2. Variants

- [ ] 2.1 `write_variants(...)`: one `variant_group`, enumerated
      `variant_index`, **no rank at insert time**.
- [ ] 2.2 A variant that fails to generate does not stop the others, and the
      ones that landed keep their rows.
- [ ] 2.3 `rank_group(...)`: apply a critic's ordering, all or nothing.
- [ ] 2.4 Parse the ordering out of critic prose. Refuse a partial, repeated or
      unknown-index ordering without writing anything.

## 3. Outcomes

- [ ] 3.1 `Repository.insert_outcome(...)`, honoring the CHECK that at least one
      of `label` / `signal` is present.
- [ ] 3.2 Nothing infers an outcome. Assert it: a ranked group has no outcomes.
- [ ] 3.3 `cost_per_accepted_artifact` returns a number once a `keep` exists,
      and excludes synthetic rows.

## 4. Wiring into the night

- [ ] 4.1 Stages that produce something write it: `brief`, `research`
      (digest), `mockups`, `build`, `critique`, `distill` (summary).
- [ ] 4.2 `build` and `mockups` write variants; the rest write single artifacts.
- [ ] 4.3 The critique stage ranks the build group after it runs.
- [ ] 4.4 **Nothing executes a generated build**, not even to check it parses.
- [ ] 4.5 A write failure fails its stage without failing the run, per the
      blocking table `night-pipeline` already established.

## 5. Verification

- [ ] 5.1 **Rank is not index**, asserted against the synthetic night whose ranks
      are a shuffled permutation. **Prove it can fail**: make the ranker write
      the index and watch it go red.
- [ ] 5.2 Corrupt a written file; `verify` reports the mismatch.
- [ ] 5.3 Two entries on one night do not collide.
- [ ] 5.4 Partial fan-out: the survivors keep their rows and files.
- [ ] 5.5 A `keep` makes the cost view return a number; synthetic rows excluded.
- [ ] 5.6 No stored path contains an absolute location.
- [ ] 5.7 Full suite, both guards, `openspec validate --strict`.

## 6. Not done here, recorded rather than dropped

- [ ] 6.1 **The rank-trust question is unanswered.** It needs five real variants
      of a real brief, generated and read by the subject. The Spark has been
      unreachable since 2 Sep and `EchoReasoner` variants would make the
      comparison meaningless. Recommendation in the proposal: treat
      `variant_rank` as the critic's opinion and never let it select what an
      outcome defaults to.
- [ ] 6.2 **No retention or deletion.** Tables are append-only; files are not.
      What "the artifact for this run" means after a cleanup is a decision, and
      guessing it here is worse than not having one.
- [ ] 6.3 **No implicit `signal` outcomes.** Those need a UI that observes the
      person — `morning-interview` and the frontend. Only `label` ships.
