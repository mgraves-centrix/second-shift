# Tasks — check the drift

## 1. The checker

- [x] 1.1 `scripts/check-drift.py`, exiting non-zero on any finding and naming
      each one with the file it is in.
- [x] 1.2 The tree check, both directions, honoring `(planned)`.
- [x] 1.3 The derived-number check, over `<!-- derived: ... -->` markers only.
      `lines <path>` and `count <glob>` — the two shapes the stale claims in
      this repository have actually taken.
- [x] 1.4 The bookkeeping check: an in-flight change with no unchecked task, and
      a canonical spec with no archived change that created it.
- [x] 1.5 It reports what it checked on success, so a green run is not read as
      more than it is.

## 2. Fix what it finds

- [x] 2.1 `ARCHITECTURE.md`: `night/` and `morning/` are built, not planned.
- [x] 2.2 `00_INDEX.md`: the `app.py` line count, marked derived rather than
      typed — 79 against a file of 80, written two days ago.
- [x] 2.3 Mark the other derived numbers that exist today, so the check has more
      than one thing to hold.

## 3. Prove every check can fail

- [x] 3.1 A test per check that constructs the failing case, and one that
      constructs the passing case so the failure is not the only outcome the
      test can produce.
- [x] 3.2 A test that an unmarked number is not reported — the false-positive
      case, which is the one that decides whether anybody keeps the gate.
- [x] 3.3 Add it to `scripts/check-mutations.py`, which is where this project
      proves its gates can fail.

## 4. Wire it in

- [x] 4.1 A row in `scripts/gate.py`, beside the two repository guards it
      belongs with.
- [x] 4.2 `docs/development/GATES.md`: the row, and what it does **not** check.
- [x] 4.3 `python3 scripts/gate.py` green, run unpiped.

## 5. Ship

- [x] 5.1 Sync, archive.
