## 1. Harness

- [x] 1.1 Measure the existing gate set end to end (36.4s).
- [x] 1.2 A browser test that seeds, serves and drives a night, hermetically, and fails on the 2 Sep playhead defect.
- [x] 1.3 A mutation check over eight shipped defects; add the lane roster test the first run showed was missing.
- [x] 1.4 One gate command, exiting with the failing gate's code; check scripts no longer change directory.
- [x] 1.5 A workflow that calls the gate command and nothing else.
- [x] 1.6 Bootstrap documented in `docs/development/GATES.md`.

## 2. Proof

- [x] 2.1 CI green on the branch: run 35220187848, all ten gates in 89.6s on the runner, 2m10s including installs.
- [x] 2.2 Identifier redaction disabled on a throwaway branch turned CI red: run 35220426474 stopped at the airlock gate in 2.3s, naming each leak, before any later gate ran. The branch is deleted.
