# Fix what would falsify the claim, while the number does not exist

## Scale classification

**L1 — Small task.** One configuration file, one property on a type that already
computes both of its inputs, one printed line. No schema change, no model call,
no credential. The argument that matters is in the file itself rather than in a
`design.md`, because the threshold is the deliverable and a design doc about it
would be a second place for it to drift.

## Why now, and not later

`EVAL_SCORING.md` and `SUBMISSION.md` both say it: *"Before scoring week 8,
write down what result would falsify the claim... A threshold chosen after the
fact is not a measurement, and a judge who has run an experiment will know."*

**Its deadline is not the submission's.** It is the moment before the week-8 run
is scored, and after that moment it cannot be set honestly at all. Today there
is exactly one eval run in the system and its `judge_model` reads
`awaiting-scoring`, so there is no number to be influenced by. That will not be
true again.

## What changes

**`config/evals/threshold.md`** — the rule, dated, with the reasoning and the
one thing it is deliberately not (a significance test). Hashed like the rubric
beside it.

**`Curve.verdict`** applies it. Both inputs already exist on the type; what was
missing was the rule and the willingness to state it before seeing the data.

**`curve` prints the verdict, the threshold's hash and the date it was fixed.**
An edit after the fact changes the hash, and it changes it in the same output
that carries the result — which is the only place a reader would look.

## The rule

Both conditions, in the same direction:

1. **Magnitude.** The mean per-prompt change exceeds twice its standard error
   across the active prompts.
2. **Consistency.** At least two thirds of the active prompts move in that
   direction.

Anything else is **"no improvement shown"**, which is not the same as "the brain
learned nothing" and the file says so.

**Per prompt, paired** — one prompt's mean is the unit, not one sample. Six
prompts differ from each other systematically, so pooling every sample into one
standard deviation mixes variation *between* prompts into an estimate meant to
capture variation *within* them.

**This corrects the recommendation `2026-09-21-add-eval-curve` recorded.** That
one said the difference had to exceed the wider of the two runs' standard
deviations. A standard deviation describes the spread of samples, not the
uncertainty of a mean, and with eighteen samples per run they differ by roughly
a factor of four — so the old rule would have reported a real improvement as not
shown. That is not caution, it is a different error, and the file records it as
a correction rather than quietly shipping the better rule.

## Found while implementing it

**The curve does not refuse two runs scored over different prompt sets.** It
refuses a different rubric, a different judge, an incomplete run, a synthetic
run and an unchanged brain — but the active set can be changed with
`evals activate`, and two runs over different prompts are two measurements of
different things in exactly the way the rubric pin exists to prevent.

Pairing per prompt makes it unavoidable rather than optional: there is no
sensible pairing across sets. Added as a sixth refusal.

## Impact

**Affected specs:** `evals` (one added requirement, one modified).

**Affected code:** `apps/api/secondshift/evals/runner.py`, `content.py`,
`__main__.py`; `config/evals/threshold.md` (new).

## Constitution Compliance

| Principle | Bearing | How this change stands |
|---|---|---|
| 1. Brain plaintext under git | **Constrains** | The claim is about two brain states, and the verdict is only meaningful because each run pins a commit. The curve already refuses two runs pinning the same one. |
| 2. The Privacy Airlock | Not engaged | Reads scores. No prompt or completion text is reachable from here. |
| 3. No empty mornings | Not engaged | — |
| 4. Text-first, voice layered | Not engaged | — |
| 5. One codebase, two deployments | **Constrains** | Synthetic runs are already refused by the curve, so a judge deployment's seeded rows cannot reach a verdict. |
| 6. Scope boundary | Respected | Evidence about the product, not part of it. |
| 7. Telemetry from line one | **Considered, deliberately not applied** | No model call, no invocation. The threshold file's hash is the record, and it is more durable than a row in the database whose contents it judges. |

No violation.

## Risk

**Setting a bar the experiment cannot clear.** Three standard errors would do
that on six prompts, which is why the rule is two — and the file says so rather
than leaving the choice looking arbitrary.

**A threshold quietly edited after the number exists.** The hash is printed
beside the verdict, and the file's addition is one `git log` away. Neither makes
it impossible; both make it visible, which is what a record is for.
