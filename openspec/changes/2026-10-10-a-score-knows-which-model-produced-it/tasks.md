## 1. The generator becomes recorded

- [ ] 1.1 `score`'s `generate` returns the recorded completion rather than text.
      A callable returning `str` is refused by name — `TypeError` carrying the
      parameter and what it got — because coercion restores the unrecorded case
      without saying so.
- [ ] 1.2 `_record_result` writes `model_call_id`. The column has existed since
      `0001_initial.sql` and the `INSERT` has never named it.
- [ ] 1.3 Every `score(...)` call site in `apps/api/tests/test_evals.py` returns
      a `Completion`. Nineteen of them; the contract changed, so they change.
      **No assertion is weakened to make one pass** — if a test stops asserting
      what it asserted, it is rewritten to assert it again.
- [ ] 1.4 Prove it fails: remove `model_call_id` from the `INSERT` and watch the
      curve's new refusal go red. If it stays green the column is being read
      from somewhere else and the guard is not guarding.

## 2. The summary can answer what produced a run

- [ ] 2.1 `RunSummary.generators` — the distinct `model_calls.model` values
      behind a run's results, read through `model_call_id`, sorted so the value
      is stable to compare and to print.
- [ ] 2.2 A result whose `model_call_id` is NULL contributes an absence rather
      than being skipped. A skipped row would make an unrecorded run look like a
      single-generator one, which is the mistake this whole change is about.
- [ ] 2.3 `summarize` prints them, so `python -m secondshift.evals summarize`
      answers "what produced this" without SQL.

## 3. The curve refuses two more ways

- [ ] 3.1 Refuse when either run records no generator, naming which. Ordered
      before the model-difference check: "I cannot see one side" is a different
      statement from "the two sides differ", and reporting the second when the
      first holds would be a guess.
- [ ] 3.2 Refuse when the two runs' generator sets differ, naming both sides.
      The message says the difference would be the model and not the brain,
      because the reader of that refusal is about to decide whether to rerun.
- [ ] 3.3 Both refusals are `NotComparable`, like the six before them, so a
      caller that handles the refusal handles these without changing.
- [ ] 3.4 A test per refusal, each asserting in isolation: construct two runs
      differing **only** in generator and assert the refusal; then make them
      agree and assert the comparison proceeds. The second half is the part that
      catches a refusal firing for the wrong reason — two mutations survived on
      23 Sep because the test's setup satisfied more than one condition at once.

## 4. Scoring becomes reachable

- [ ] 4.1 A `score` command in `evals/__main__.py`, taking a run id, resolving
      the judge from configuration and the generator from the reasoner registry.
- [ ] 4.2 With no judge configured it exits non-zero naming what is missing —
      which is today's state, and the point is that the shell can now see it
      instead of the absence being invisible from the command list.
- [ ] 4.3 `is_synthetic` stays `synthetic_flag()`, never a flag on the command.
      A judge deployment that scored itself into the real curve is unrecoverable.
- [ ] 4.4 A test that runs `main(["score", ...])` against a temporary database
      with no judge, asserting the exit code and that no `eval_results` row was
      written. The runner's refusal is already tested; this tests that the
      command reaches it.

## 5. The documents agree about the count

- [ ] 5.1 `docs/SPEC_ROADMAP.md` says the curve "refuses five ways" and
      `docs/SUBMISSION.md` says six. After this change it is eight. Both derive
      the figure with a marker rather than stating it, so `check-drift.py` fails
      when it moves again.
- [ ] 5.2 The drift gate prints, on every pass, that it does not check whether
      two documents agree. This disagreement is that gap, found by reading, and
      the fix is to stop hand-writing the number in two places.

## 6. Verification

- [ ] 6.1 One mutation in `scripts/check-mutations.py`: the generator refusal
      removed, the gate that must go red named.
- [ ] 6.2 The orphan check — `RunSummary.generators` and the `score` command are
      both referenced from outside their own module, which is the thing this
      change exists to fix in the first place.
- [ ] 6.3 `python3 scripts/gate.py` green, run unpiped so the exit code is the
      gate's own.
