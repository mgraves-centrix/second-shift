## 1. Enforce the pinning at scoring

- [x] 1.1 Add a typed error for a rubric that is not the one a run pinned, alongside `NoJudgeConfigured`.
- [x] 1.2 Compare the given rubric's hash against the run's `rubric_sha` in `score`, before generation, naming the run and both hashes on mismatch.
- [x] 1.3 Test: scoring a run with a different rubric fails, records no `eval_results`, and leaves the run awaiting scoring.
- [x] 1.4 Test: scoring with the pinned rubric proceeds and records results as before.
- [x] 1.5 Test: a refused score writes no failure rows, because the run did not partially succeed.

## 2. Make the pinning readable

Independent of group 1; may run in parallel.

- [x] 2.1 Read every recorded eval run — id, week, `rubric_sha`, `brain_sha`, awaiting state — through the runner rather than by hand-written SQL at the call site.
- [x] 2.2 Report them from `status` beside the hash of the rubric file on disk.
- [x] 2.3 State plainly when a recorded run pins a rubric that is not the file on disk, and exit non-zero.
- [x] 2.4 Report agreement, and the no-runs case, explicitly rather than by silence.
- [x] 2.5 Test: a run pinned to a different rubric is reported as such and the command exits non-zero.
- [x] 2.6 Test: agreement exits zero and says so.
- [x] 2.7 Test: an empty database reports the rubric on disk and exits zero.

## 3. Stop deployment destroying the evidence

Depends on nothing in groups 1-2.

- [x] 3.1 Hash the target's rubric before the tree is replaced, reporting a definite `absent` when there is none.
- [x] 3.2 Refuse the deploy when the hashes differ, printing both, the command that retrieves the target's copy, and the override.
- [x] 3.3 Accept an explicit override that proceeds and says what it is replacing.
- [x] 3.4 Verify with `bash -n`, and by running the script against stubbed `ssh` and `npm` so the guard's decision is exercised. `shellcheck` was not available in this environment, and the guard has not run against a real target from here.

## 4. Gates

- [x] 4.1 Gate: full Python suite passes.
- [x] 4.2 Gate: web tests and typecheck pass, unchanged.
- [x] 4.3 Gate: `openspec validate --strict` for this change and every canonical spec.
- [x] 4.4 Gate: both check scripts pass.
- [x] 4.5 Gate: the new tests fail with the implementation reverted.
