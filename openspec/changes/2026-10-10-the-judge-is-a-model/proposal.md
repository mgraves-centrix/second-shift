# The judge is a model, and scoring is a command

## Scale classification

**L2 — Feature.** One capability (`evals`), two files
(`evals/judge.py`, `evals/__main__.py`), under a day. It adds the first
implementation of an interface that has existed since 2 Sep and the entry point
that calls it. No migration, no new provider: the judge drives a `Reasoner`,
which already exists in two forms.

## Why

**Nothing in this system has ever scored anything.** `Judge` is a Protocol with
a strict parse behind it and one implementation — `StubJudge`, which returns
arithmetic on the length of its input. The submission's centerpiece is a week-1
to week-8 comparison of scores, and the only eval run in the database reads
`judge_model = 'awaiting-scoring'`.

Week 8 is **15–21 Oct**. The baseline has to be generated and scored, and the
week-8 run generated and scored, inside that window with the same judge on both
sides — the curve refuses two judges, correctly, as two instruments. There is
no judge yet to be the same one.

**The parse is the hard part and it is already done.** `Judgement.parse` refuses
a missing dimension, a non-integer, a boolean, a value outside 1–5, and anything
that is not an object. What is missing is the twenty lines that ask a model for
those numbers and the entry point that runs it.

**And it does not need a credential.** The judge drives `Reasoner`, so it works
against the local server as readily as a cloud one, and `VllmStub` in the test
suite is a real OpenAI-compatible endpoint on a socket. That makes this
implementable and verifiable without a Nebius key — against a stub here, and
against the real local reasoner on the machine.

## The open decision

**Which model grades, and under which policy.**

`docs/MODELS.md` binds the eval judge to `Nemotron-3-Ultra-550B-a55B` via Token
Factory, and says it is version-pinned in `eval_runs.judge_model_version` and
never floats. That is a decision of record and this change does not overturn it.
But it was made on 27 Aug for judgment quality, and two things about it are now
worth re-examining rather than inheriting:

**It makes the centerpiece depend on a credential.** The key exists on the
always-on machine and nowhere else. A local judge needs no key, and the machine
session that the week-8 run requires anyway — the local reasoner generates the
outputs — would then close the whole thing.

**It sends brain-derived text to a remote provider.** An eval output is
generated from the brain at a pinned commit. Principle 2 says the brain itself
never leaves and only assembled, policy-filtered context is transmitted. An
output is not the brain, and it is not retrieval context either; it is model
text about the subject's own ideas. Nothing in `openspec/specs/privacy-airlock/`
or `docs/decisions/` says which of those it counts as, and the judge's
`model_calls` row has to carry a policy either way.

The argument the other way is judgment quality: a 550B grader is a better
instrument than a 30B one. The counter is that the curve uses **differences**,
not levels, and the judge is pinned across both runs — so a consistent judge
matters and an excellent one is a bonus. A 30B model emitting five integers
against a written rubric is not the hard end of its range.

- [NEEDS CLARIFICATION: Does an eval output sent to a cloud judge require
  redaction before egress, or is it `cloud-assisted` text the airlock already
  permits? The judge's `model_calls` row records `policy` and
  `redaction_applied`, so this decides what those two columns say — and whether
  a `local-only` entry's eval output may be graded remotely at all.]
- [NEEDS CLARIFICATION: Is the judge the cloud Ultra model as `docs/MODELS.md`
  binds it, or the local reasoner? Recommendation: **the local reasoner for the
  week-1 and week-8 runs**, because it removes the credential from the critical
  path with eleven days to the window, needs no answer to the question above,
  and the comparison is of differences under a pinned judge rather than of
  absolute scores. Revisit for a later run if the grader looks like the limit.]

**Neither marker blocks what this change builds.** `ModelJudge` takes a
`Reasoner` and a policy; both answers are a constructor argument. What they
block is the `score` command's default and the deployment note, so those are the
tasks held back until `/openspec:clarify` resolves them.

## What this change is not

- **Not a Nebius provider.** `TokenFactoryReasoner` is `nebius-executor`'s, and
  building it here would prejudge the second marker. The judge works against
  any `Reasoner`.
- **Not a change to the rubric, the prompts or the threshold.** All three are
  files, pinned by hash, and this change reads them.
- **Not a prose parser.** See below: one rule, and a refusal otherwise.

## What changes

1. **`ModelJudge`** in `evals/judge.py`. Takes a `Reasoner`, a policy and a
   pinned version string; reports `name` from `reasoner.model`, so no model
   identifier appears outside `providers/`.

2. **The judgement is the last JSON object in the completion**, and anything
   else refuses. The served checkpoint emits deliberation inconsistently —
   sometimes inside `<think>`, sometimes as bare prose, which
   `agents/invoke.py` records as the finding it is. A rule that reads the last
   top-level `{...}` and parses it skips deliberation without guessing at it,
   and needs no delimiter to be present. It is **not** prose extraction: the
   numbers are never read from text, only from an object that parsed.

3. **A truncated completion is refused before it is parsed.** `Completion`
   carries `finish_reason`, and JSON cut off at a token limit can still parse
   as a smaller valid object — five dimensions becoming three, scored. This is
   the failure mode the first real night had: three turns ran out of tokens
   inside their deliberation and later stages read the unfinished notes as
   input.

4. **A `score` command**, so a recorded baseline can be generated and graded
   outside the test suite. `EvalRunner.score` is called from nowhere but
   `apps/api/tests/test_evals.py`, and that module's docstring says scoring is
   "deliberately absent from this entry point until a judge is chosen and a
   generating provider is configured" — which is exactly the condition this
   change ends.

5. **`is_synthetic` stays server-derived.** A judge deployment that scored
   itself into the real curve is unrecoverable, and the command takes no flag
   that could do it.

## Impact

- `apps/api/secondshift/evals/judge.py` — `ModelJudge`, and the extraction rule.
- `apps/api/secondshift/evals/__main__.py` — the `score` command, and the
  docstring that currently says scoring is absent.
- `apps/api/tests/test_evals.py` — the judge against `VllmStub`: each shape it
  must read, each it must refuse.
- `scripts/check-mutations.py` — the truncation refusal, which is the one whose
  absence is silent.

## Constitution Compliance

- **Principle 1 (the brain is plaintext under git).** Untouched. Generation
  still reads the brain at the pinned commit; the judge never sees the brain,
  only one output and the rubric.
- **Principle 2 (Privacy Airlock).** **The first marker above is this
  principle**, which is why it is a marker and not an assumption. What the
  change itself does is make the policy an explicit constructor argument that
  `Reasoner.complete` asserts at every call, so no judge can run without one
  being named. A local judge raises no question; a cloud judge is blocked on the
  answer rather than proceeding under a guess.
- **Principle 3 (no empty mornings).** Not in the night path.
- **Principle 4 (text-first).** No interaction surface.
- **Principle 5 (one codebase, two deployments).** No model identifier leaves
  `providers/`: `ModelJudge.name` reads `reasoner.model` at runtime. Nothing
  branches on which instance is running.
- **Principle 6 (scope boundary).** Inside `evals`.
- **Principle 7 (telemetry from line one).** The judge's call is a model call
  and is recorded by `Reasoner.complete` before `ModelJudge` sees the text —
  the base class records, the implementation cannot forget. A refused judgement
  still leaves the call recorded, which is the case that matters: a judge that
  failed to produce readable scores still cost tokens.

## Risk

**A judge that refuses everything is worse than no judge**, because it reads as
the system working and produces an incomplete run. The extraction rule is the
whole risk surface, so every shape is a test: bare JSON, a fenced block, prose
then JSON, deliberation then JSON, two objects, prose only, truncated, and
scores outside the range. The mutation is the truncation refusal, because that
is the one that fails silently — a smaller valid object, scored.

**The stub is not the model.** Everything here can pass against `VllmStub` and
still fail on the first real completion, because what a real checkpoint emits
around its JSON is not something a stub can predict. That is named rather than
mitigated: the first real run on the machine is the verification, and it is a
task in this change rather than a hope.
