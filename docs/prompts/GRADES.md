# Prompt grades

Run `python3 scripts/grade-prompts.py` rather than trusting this file. A grade
that was claimed instead of computed is not a grade.

```
all 17 prompts at 12/12
```

## What the score does and does not prove

**It proves presence, not quality.** The grader checks that each prompt has a
named open decision, a runnable loop, a verification step that can fail, explicit
non-goals, and a report that demands honesty. It cannot check whether the open
decision is the *sharp* one, or whether the facts are true.

Criterion 1 — "grounded in verified fact" — is the weakest check by far. It
matches the phrase `do not invent any of it`, which is a proxy for a discipline,
not a measurement of it. **The facts in these prompts were verified by hand**
against the running machine and the schema on 2 Sep: row counts read from the
database over the tailnet, the reasoner's response shape read from a live
completion, the environment variables enumerated from the source, the absent
files confirmed absent. Nothing in the grader would catch it if a later edit put
a wrong number in.

Treat 12/12 as *this prompt has the parts a good prompt has*. Whether it is a
good prompt is a question for the session that uses it, and the report format is
what surfaces the answer.

## The set was incomplete, which no grade would have caught

The first twelve prompts all scored 12/12 and the set was still missing four
layers. A rubric measures whether a prompt is well made; it says nothing about
whether the right prompts exist.

`API_LAYER.md`, `EVAL_SCORING.md`, `OPERATIONS.md` and `ASR.md` were added after
review. Two of those gaps were structural rather than merely absent:

- **The index named two collision surfaces and there were three.**
  `api/app.py` is a single 368-line file that five sessions need to add routes
  to, so those five would have serialized on it. Naming the surface wrongly is
  worse than not naming it, because the sequencing table looked authoritative.
- **`SUBMISSION.md` declared a dependency on a week-8 eval run that nothing
  produced.** The submission's centerpiece — the comparison the whole thesis
  rests on — had no owner, and the dependency was written down in a way that read
  as satisfied.

Both were found by being asked "is anything missing?", not by grading.

## A prompt excluded from grading is not the same as a prompt below the bar

`OVERNIGHT.md` sat in the grader's exclusion list from the start, alongside
`00_INDEX.md` and `GRADES.md` — but for a different reason than either of
those. It was not written to this rubric; it predated it, carried a work
queue that went stale within a day of being read (see its own file for what
that cost), and was never held to the same twelve checks the rest of this set
passes. Excluding it was accurate at the time and stopped being accurate the
moment it was rewritten on 2 Sep to be judged by the same bar as everything
else here — at which point leaving it excluded would have been the thing this
whole file warns against: a grade nobody computed, standing in for one that
was never asked. It is graded now, listed in the set below, and reached
12/12 the same way everything else did — by fixing the prompt, not the
regex. `NIGHT_SCRUBBER.md` stays excluded; nothing about it changed.

## First-pass failures, and what fixed them

Every prompt was graded before commit. Seven failed — the table below is the
count. The fixes are listed because a grade with no named weakness behind it is
a claim, not a finding, and for a while this line said six against seven rows.

| Prompt | First pass | Missing | Fix |
|---|---|---|---|
| `NEBIUS_EXECUTOR.md` | 9/12 | No open-decision section; no by-preference guard; no honesty demand | Added a section saying the decisions are all upstream markers and must not be answered in-session, and a report item asking whether the fan-out actually beat one machine |
| `AGENTS.md` | 10/12 | No proof the sha test can fail; no honesty demand | Added "hardcode the sha and watch the suite go red"; added "if the brief still opens with *Here's a thinking process*, say so" |
| `ARTIFACTS.md` | 11/12 | Can-fail proof implied, not instructed | Added "replace the critic's rank with the generation index and watch it go red" |
| `JUDGE_MODE.md` | 11/12 | No way to reach the starting state; no mutation check | Added the seed-and-serve commands; added two can-fail proofs including inserting a non-synthetic row |
| `SUBMISSION.md` | 11/12 | No falsification of its own verification | Added "change one figure and confirm the regeneration disagrees" |
| `TEST_HARNESS.md` | 11/12 | Can-fail phrasing ambiguous | Made the browser-test mutation explicit, citing the playhead defect that shipped through three passing tests |
| `OVERNIGHT.md` | 11/12 | Verification discipline was described in the abstract — never a concrete instruction to watch a specific check fail | Added the instruction to break the guard a shipped capability's argument rests on and confirm the suite goes red before trusting it green, citing the same playhead defect by what actually caused it: every check read the ARIA value, not where the element rendered |

## Three grader bugs, which are the point

The first version of the checker reported `NEBIUS_EXECUTOR.md` and
`SUBMISSION.md` as failing criteria they satisfied. Both were the checker's
fault: a line break split `by preference` across two lines, and the pattern
accepted `able to fail` but not `can fail`.

The fix was to normalize whitespace and widen the pattern — **not** to reword the
prose so it matched a bad regex. Bending the artifact to satisfy the test is the
failure mode this whole repository is written against, and it would have been
invisible in a green result.

The third bug was this file. The grader scored `GRADES.md` as a prompt and failed
it on seven criteria, correctly — a report card has no runnable loop. Scoping the
grader to actual prompts fixed it. Three bugs in a checker that fits on one
screen is the argument for running it rather than trusting a number pasted into a
document.
