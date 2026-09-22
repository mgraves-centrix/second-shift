# Tasks — supervise the reasoner

The switch is three commands on the always-on machine and this session has no
route to it. What ships here is what can be made correct in advance.

## 1. The precondition

- [x] 1.1 `ops night-status`: exit 0 idle, exit 3 when a night holds the lock,
      reusing the night's own `EXIT_ALREADY_RUNNING` so the two commands cannot
      answer the same state differently.
- [x] 1.2 It reads the lock, not an open run — an open run is also what a night
      killed last week leaves behind.
- [x] 1.3 A missing lock file is idle, not an error. A judge container has never
      run a night and is not broken.
- [x] 1.4 `doctor` reports the same state as a line, and a night in flight is
      not a fault.
- [x] 1.5 Tests for all four, with the lock genuinely held by another process
      rather than simulated — the thing under test is a `flock`, and faking it
      would test the fake.

## 2. The procedure

- [x] 2.1 `docs/operations/SUPERVISING_THE_REASONER.md`: the steps in order,
      each saying what it protects.
- [x] 2.2 The container-name step first, with the failure it prevents spelled
      out — a unit restarting every fifteen seconds while the reasoner appears
      healthy, because the old container still holds the port the probe checks.
- [x] 2.3 Verification afterwards: `ops doctor`, and the probe reporting the
      reasoner by name on the port `config/models.toml` allocates.

## 3. Record it

- [x] 3.1 Answer the marker in `2026-09-21-add-operations`'s archived design, in
      place.
- [x] 3.2 `docs/SPEC_ROADMAP.md`: the ledger row becomes the procedure plus the
      trap, rather than an undecided question.

## 4. Ship

- [ ] 4.1 `python3 scripts/gate.py` green, run unpiped.
- [ ] 4.2 Sync, archive.
