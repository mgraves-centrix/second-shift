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

**Scale note.** This is L2 and not L1 because the extraction rule is a
specification decision, not an implementation detail: what counts as a readable
judgement determines which real completions become scores and which become
recorded failures.

## The decision this deliberately does not make

**Which model grades, and under which policy**, is
`openspec/changes/2026-10-10-which-model-grades/`. It carries two
`[NEEDS CLARIFICATION]` markers and is blocked on `/openspec:clarify`, and the
`score` command goes with it because its default is one of the answers.

This change is separate precisely so that question does not hold the judge. The
apply gate blocks implementation while any marker stands — correctly — and with
eleven days to the week-8 window, a judge that exists and is tested is worth
more than a judge waiting on a decision about its constructor arguments.
`ModelJudge` takes a `Reasoner` and a policy; both answers are a call site.

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


## Impact

- `apps/api/secondshift/evals/judge.py` — `ModelJudge`, and the extraction rule.
- `apps/api/tests/test_evals.py` — the judge against `VllmStub`: each shape it
  must read, each it must refuse.
- `scripts/check-mutations.py` — the truncation refusal, which is the one whose
  absence is silent.

## Constitution Compliance

- **Principle 1 (the brain is plaintext under git).** Untouched. Generation
  still reads the brain at the pinned commit; the judge never sees the brain,
  only one output and the rubric.
- **Principle 2 (Privacy Airlock).** The policy is an explicit constructor
  argument, which `Reasoner.complete` asserts at every call, so no judge can run
  without one being named. **What the policy should be for a cloud judge is a
  marker in the companion change**, not an assumption here: an eval output is
  model text generated from the brain at a pinned commit, and nothing in
  `openspec/specs/privacy-airlock/` or `docs/decisions/` says whether that
  counts as context the airlock already permits. This change makes the question
  unavoidable at the call site rather than answering it.
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
