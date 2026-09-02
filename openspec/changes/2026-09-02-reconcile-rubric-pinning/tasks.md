## 1. Enforce the pinning at scoring

- [ ] 1.1 Add a typed error for a rubric that is not the one a run pinned, alongside `NoJudgeConfigured`.
- [ ] 1.2 Compare the given rubric's hash against the run's `rubric_sha` in `score`, before generation, naming the run and both hashes on mismatch.
- [ ] 1.3 Test: scoring a run with a different rubric fails, records no `eval_results`, and leaves the run awaiting scoring.
- [ ] 1.4 Test: scoring with the pinned rubric proceeds and records results as before.
- [ ] 1.5 Test: a refused score writes no failure rows, because the run did not partially succeed.

## 2. Make the pinning readable

Independent of group 1; may run in parallel.

- [ ] 2.1 Read every recorded eval run — id, week, `rubric_sha`, `brain_sha`, awaiting state — through the runner rather than by hand-written SQL at the call site.
- [ ] 2.2 Report them from `status` beside the hash of the rubric file on disk.
- [ ] 2.3 State plainly when a recorded run pins a rubric that is not the file on disk, and exit non-zero.
- [ ] 2.4 Report agreement, and the no-runs case, explicitly rather than by silence.
- [ ] 2.5 Test: a run pinned to a different rubric is reported as such and the command exits non-zero.
- [ ] 2.6 Test: agreement exits zero and says so.
- [ ] 2.7 Test: an empty database reports the rubric on disk and exits zero.

## 3. Stop deployment destroying the evidence

Depends on nothing in groups 1-2.

- [ ] 3.1 Hash the target's rubric before the tree is replaced, reporting a definite `absent` when there is none.
- [ ] 3.2 Refuse the deploy when the hashes differ, printing both, the command that retrieves the target's copy, and the override.
- [ ] 3.3 Accept an explicit override that proceeds and says what it is replacing.
- [ ] 3.4 Verify with `bash -n`, and with `shellcheck` if available. Note in the change that the guard was not executed against a real target from this window.

## 4. Gates

- [ ] 4.1 Gate: full Python suite passes.
- [ ] 4.2 Gate: web tests and typecheck pass, unchanged.
- [ ] 4.3 Gate: `openspec validate --strict` for this change and every canonical spec.
- [ ] 4.4 Gate: both check scripts pass.
- [ ] 4.5 Gate: the new tests fail with the implementation reverted.
