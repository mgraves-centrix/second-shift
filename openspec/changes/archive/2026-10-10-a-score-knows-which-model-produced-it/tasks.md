## 1. The generator becomes recorded

- [x] 1.1 `score`'s `generate` returns the recorded completion rather than text.
      A callable returning `str` is refused by name — `TypeError` carrying the
      parameter and what it got — because coercion restores the unrecorded case
      without saying so.
- [x] 1.2 `_record_result` writes `model_call_id`. The column has existed since
      `0001_initial.sql` and the `INSERT` has never named it.
- [x] 1.3 Every `score(...)` call site in `apps/api/tests/test_evals.py` returns
      a `Completion`. Nineteen of them; the contract changed, so they change.
      **No assertion is weakened to make one pass** — if a test stops asserting
      what it asserted, it is rewritten to assert it again.
- [x] 1.4 Prove it fails: remove `model_call_id` from the `INSERT` and watch the
      curve's new refusal go red. If it stays green the column is being read
      from somewhere else and the guard is not guarding.

## 2. The summary can answer what produced a run

- [x] 2.1 `RunSummary.generators` — the distinct `model_calls.model` values
      behind a run's results, read through `model_call_id`, sorted so the value
      is stable to compare and to print.
- [x] 2.2 A result whose `model_call_id` is NULL contributes an absence rather
      than being skipped. A skipped row would make an unrecorded run look like a
      single-generator one, which is the mistake this whole change is about.
- [x] 2.3 `summarize` prints them, so `python -m secondshift.evals summarize`
      answers "what produced this" without SQL.

## 3. The curve refuses two more ways

- [x] 3.1 Refuse when either run records no generator, naming which. Ordered
      before the model-difference check: "I cannot see one side" is a different
      statement from "the two sides differ", and reporting the second when the
      first holds would be a guess.
- [x] 3.2 Refuse when the two runs' generator sets differ, naming both sides.
      The message says the difference would be the model and not the brain,
      because the reader of that refusal is about to decide whether to rerun.
- [x] 3.3 Both refusals are `NotComparable`, like the six before them, so a
      caller that handles the refusal handles these without changing.
- [x] 3.4 A test per refusal, each asserting in isolation: construct two runs
      differing **only** in generator and assert the refusal; then make them
      agree and assert the comparison proceeds. The second half is the part that
      catches a refusal firing for the wrong reason — two mutations survived on
      23 Sep because the test's setup satisfied more than one condition at once.

## 4. Scoring becomes reachable — moved

Moved to the judge's own change. `evals/__main__.py` says scoring is
"deliberately absent from this entry point until a judge is chosen and a
generating provider is configured", and a `score` command added here could only
ever refuse — the same unreachable shape in a different costume. The entry point
and the thing it calls arrive together, or the design decision gets made under
time pressure at the worst moment.

## 5. The documents agree about the count

- [x] 5.1 `docs/SPEC_ROADMAP.md` says the curve "refuses five ways" and
      `docs/SUBMISSION.md` says six. After this change it is eight. Both derive
      the figure with a marker rather than stating it, so `check-drift.py` fails
      when it moves again.
- [x] 5.2 The drift gate prints, on every pass, that it does not check whether
      two documents agree. This disagreement is that gap, found by reading, and
      the fix is to stop hand-writing the number in two places.

## 6. Verification

- [x] 6.1 One mutation in `scripts/check-mutations.py`: the generator refusal
      removed, the gate that must go red named.
- [x] 6.2 The orphan check — `RunSummary.generators` and `generators_text` are
      referenced from outside their own module, which is the thing this change
      exists to fix in the first place.
- [x] 6.3 `python3 scripts/gate.py` green, run unpiped so the exit code is the
      gate's own.
