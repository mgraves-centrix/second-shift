# Tasks — schedule the backup

## 1. The guard the schedule creates

- [x] 1.1 `create_backup` refuses a destination on the same device as the
      database, with `--same-device-ok` to proceed deliberately. The refusal
      names the flag: a rehearsal is a real use, and an obstruction that does
      not say how to proceed is one somebody routes around.
- [x] 1.2 A test for the refusal, and one for the flag. Both construct the
      case rather than describing it.
- [x] 1.3 `doctor` reports a newest backup that sits on the database's own
      device. Weeks of successful local backups is a state to be told about,
      not to discover.

## 2. The unit

- [x] 2.1 `deploy/spark/second-shift-backup.user.service` — `oneshot`,
      `After=second-shift-night.service`, destination from
      `%h/.config/second-shift/backup.env` with no leading `-` so a missing
      file fails loudly.
- [x] 2.2 `Wants=second-shift-backup.service` on the night's unit, which is
      what makes it run after a failed night too.
- [x] 2.3 Extend `test_deploy_units.py`: the ordering, the coupling, the
      required environment file, and that the unit does not carry a
      destination — this repository is public and a NAS path is environment.

## 3. Record the answer where it was asked

- [x] 3.1 Annotate the marker in `2026-09-21-add-operations`'s archived design
      with the resolution, in the house style — the nebius proposal writes
      "**Resolved: …**" under its own questions rather than deleting them.
- [x] 3.2 `docs/operations/RECOVERY.md`: the schedule, and the rehearsal's flag.
- [x] 3.3 `docs/SPEC_ROADMAP.md`: the ledger row for the schedule now says what
      a machine session installs rather than what is undecided.

## 4. Ship

- [ ] 4.1 `python3 scripts/gate.py` green, run unpiped.
- [ ] 4.2 Sync, archive.
