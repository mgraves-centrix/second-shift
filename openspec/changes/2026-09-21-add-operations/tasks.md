# Tasks — operations

Neither clarification marker blocks implementation. The first asks where
backups are kept and how often; the tool takes a destination as a required
argument, so it blocks the schedule and not the mechanism. The second asks when
the reasoner container becomes a supervised unit, which is an action on a
machine this session cannot reach. Both are answered by the user; everything
below proceeds without them.

## 1. Prove the thing that would otherwise be assumed

- [ ] 1.1 A test that copies a WAL-mode database two ways under a concurrent
      writer — the file alone, and the online backup API — and asserts the naive
      copy is missing committed data while the online copy has all of it and
      passes `integrity_check`. This is the argument for the whole mechanism and
      it belongs in the suite, not only in `design.md`.

## 2. The backup

- [ ] 2.1 `secondshift/ops/` with `python -m secondshift.ops` as its entry
      point, matching `night/`, `evals/` and `brain/`.
- [ ] 2.2 `backup`: the database through `Connection.backup()`, the artifacts
      tree, and a manifest carrying per-table row counts, `schema_version`, the
      artifact count and total bytes, a digest per member and the instant.
- [ ] 2.3 The destination is required and has no default.
- [ ] 2.4 It states what the archive contains — unredacted captured text and
      recorded model payloads — every time it writes one.
- [ ] 2.5 The manifest names the brain as excluded, with the reason.

## 3. Restore and verify

- [ ] 3.1 `verify`: check a backup against its own manifest without restoring
      it, and name the member that disagrees.
- [ ] 3.2 `restore`: rebuild onto a path, refuse an existing database unless the
      overwrite is explicit, and say what is already there.
- [ ] 3.3 After restoring, compare the result against the manifest — counts and
      schema version — and fail loudly on disagreement.
- [ ] 3.4 Prove each refusal can fail: a corrupted member, a mismatched count, a
      restore onto an occupied path.

## 4. Doctor

- [ ] 4.1 Every check from the design's table, each reporting rather than
      stopping at the first failure.
- [ ] 4.2 Non-zero exit when any check fails, zero when all pass.
- [ ] 4.3 Prove every check can fail by breaking the thing it checks. A check
      that cannot go red reads as evidence while proving nothing.
- [ ] 4.4 It runs where the reasoner is absent and reports that, rather than
      raising — the judge container is exactly that machine.

## 5. The units and the deploy

- [ ] 5.1 Test that both reasoner units bind loopback. The running container
      publishes on every interface, and that difference is the one part of the
      reconciliation that is a privacy question rather than an uptime one.
- [ ] 5.2 `deploy.sh` takes a backup before it destroys anything, and refuses
      the deploy if the backup fails.
- [ ] 5.3 Extend the stub-based deploy guard tests to cover it.

## 6. The procedure

- [ ] 6.1 `docs/operations/RECOVERY.md`: what is lost in the worst case, the
      steps in order, and **per step, whether it has been executed and against
      what.**
- [ ] 6.2 Execute the whole procedure here against a seeded database with a
      writer active. Record the measured time and the measured sizes.
- [ ] 6.3 List every step that needs the machine in `docs/SPEC_ROADMAP.md`, not
      only in the procedure.

## 7. Ship

- [ ] 7.1 `python3 scripts/gate.py` green, all ten, run unpiped so its exit
      status is its own.
- [ ] 7.2 Sync, archive, and record what a machine session owes.
