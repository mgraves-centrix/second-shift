# Which model grades, and under which policy

## Scale classification

**L2 — Feature.** One capability (`evals`), one file
(`evals/__main__.py`), under a day — once the two questions below are answered.
It is separate from `2026-10-10-the-judge-is-a-model` because the apply gate
blocks implementation while a clarification marker stands, and `ModelJudge`
itself needs neither answer.

## Why

`ModelJudge` takes a `Reasoner` and a policy. Something has to choose them, and
the choice is not a coding decision.

## The decision, resolved 10 Oct

**The local reasoner grades. Its calls run `local-only`, and the cloud judge
ADR 0006 named is retired rather than deferred.**

### What settles it

**ADR 0010 had already made a cloud judge impermissible, and nobody noticed for
five weeks.** It says brain topic files carry `local-only`, and its rationale is
explicit about why the restriction travels: "treating the output as less
restricted than its most restricted input would launder the policy." Eval
generation reads `topic_files_at(brain_sha)` — brain topic files — so an eval
output is distilled from `local-only` material and inherits that policy by
0010's own argument. The constitution then forbids a `local-only` idea reaching
a remote provider, enforced as a `CHECK` on `model_calls`, and says proposals
MUST NOT weaken, bypass or make that constraint conditional.

So the judge was never a free choice between two instruments. ADR 0006 bound it
to `Nemotron-3-Ultra-550B-a55B` on **27 Aug**; ADR 0010 contradicted that clause
on **2 Sep**; both have been accepted and in force since. The disagreement
survived because nothing in this system had ever scored anything — the only
recorded eval run reads `judge_model = 'awaiting-scoring'`, so the dead clause
was never executed and never failed.

### What follows from it

- **The judge is the local reasoner**, driven through `ModelJudge` and the
  `Reasoner` interface, with `policy="local-only"`. The `model_calls` CHECK then
  holds by construction rather than by review.
- **No redaction question arises**, because nothing leaves the machine. The
  question of whether an eval output is redactable `cloud-assisted` text is not
  answered here and does not need to be; it returns only if someone proposes a
  cloud judge, and that proposal must supersede ADR 0010 first.
- **The schedule argument is real but secondary.** A local judge does take the
  credential off the critical path with the week-8 window opening 15 Oct, and
  the curve compares differences under a pinned judge rather than absolute
  scores, so a consistent 30B grader is sufficient. Those were the reasons
  offered before the 0010 conflict was found. They are no longer the reasons:
  the airlock is.

### What it costs

A 550B grader is a better instrument than a 30B one, and this gives that up. The
claim being measured is a difference across two pinned brain states under one
pinned judge, so the loss is in the absolute level of the scores rather than in
the comparison — but it is a real loss and it is not being pretended away.

**This change writes the ADR that records all of it**, superseding ADR 0006's
eval-judge clause alone. The rest of 0006's bindings stand; an accepted decision
is superseded by a new record, never edited.

## What this change is not

- **Not the judge.** `2026-10-10-the-judge-is-a-model` builds and tests that.
- **Not a Nebius provider.** The resolution retires the cloud judge, so no
  Token Factory client is needed here or implied. If one is ever built it is
  `nebius-executor`'s, and a judge running through it would need ADR 0010
  superseded first.
- **Not a reversal of ADR 0010.** It is reaffirmed. Moving the judge to a remote
  provider means superseding it with an argument, not setting a flag — 0010 says
  so itself, because "a switch that could be flipped is a switch that will be".

## How an answer is generated, decided 10 Oct

**Through `agents.invoke`, the way the product produces work** — the `architect`
role, `task` set to the eval prompt, `context` set to the brain's topic files at
the pinned commit.

`EvalRunner.score` hands `generate` the brain and leaves composition to the call
site, and nothing in the codebase composes topic files into a turn:
`retrieval/index.py` indexes them as documents, and no path turns them into a
prompt. So the alternative was a composition existing only for evals, and a
week-8 improvement in it would be an improvement in the harness rather than
demonstrably in the product. `architect` because the candidate set is
idea-interrogation shaped and *interrogation* is the rubric's first dimension.

**This reintroduces the hole `a-score-knows-which-model-produced-it` closed, one
layer up**, and so closes it the same way. A role prompt is versioned —
`distiller` is already at v2 — and `eval_runs` pins `brain_sha`, `rubric_sha`,
`code_sha` and the judge, but no prompt. A prompt edited between week 1 and
week 8 would read as the brain having learned, which is exactly the defect the
generator refusal exists to prevent.

It needs no migration. `eval_results.model_call_id` →
`model_calls.agent_invocation_id` → `agent_invocations.agent_id` →
`agents.prompt_sha`, which also carries `role` and `version`. The join is
already there; only the read and the refusal are new.

## What changes

1. **A `score` command** in `evals/__main__.py`, resolving the judge and the
   generating reasoner from configuration, so a recorded baseline can be
   generated and graded outside the test suite. `EvalRunner.score` is currently
   called from nowhere but `apps/api/tests/test_evals.py`, and that module's
   docstring says scoring is "deliberately absent from this entry point until a
   judge is chosen and a generating provider is configured" — the condition the
   resolution above ends. Both are the local reasoner: the judge by this
   decision, the generator because the brain never leaves the machine.

2. **The judge's pinned version** recorded in `eval_runs.judge_model_version`,
   from configuration rather than from whatever the endpoint reports, because
   ADR 0006 says it never floats and that clause of it survives. The local
   server reports whatever `--served-model-name` was set to at launch, so a
   version read from the endpoint floats the moment it is restarted against
   another checkpoint.

3. **`is_synthetic` stays server-derived.** A judge deployment that scored
   itself into the real curve is unrecoverable, and the command takes no flag
   that could do it.

4. **An ADR superseding ADR 0006's eval-judge clause**, recording that ADR 0010
   had already made a cloud judge impermissible and that the clause has been
   dead since 2 Sep. The rest of 0006's bindings stand, and 0006 itself is not
   edited — an accepted decision is superseded by a new record.

5. **`docs/MODELS.md` stops stating the retired clause as current.** It
   tabulates ADR 0006, so its "frontier turns, eval judge" row is where a reader
   would next pick up the dead binding.

6. **`AgentTurn` carries the model call it recorded.** It carries `role`,
   `text`, `raw_text` and `invocation_id` and not the call id, so a caller that
   needs the row — which is now every eval result — cannot name it. One field,
   read from the completion the turn already holds.

7. **A tenth refusal in the curve**: the two runs' outputs were produced by
   different agent prompts. Absent on both sides compares equal, unlike the
   generator, because generating without an agent is a legitimate shape; what is
   refused is a *change* between the runs.

## Impact

- `apps/api/secondshift/evals/__main__.py` — the `score` command.
- `apps/api/secondshift/agents/invoke.py` — `AgentTurn` carries its
  `model_call_id`. **Outside `evals`**, and the only file in this change that is.
- `apps/api/secondshift/evals/runner.py` — the prompt versions behind a run, and
  the refusal that reads them.
- `config/models.toml` — the judge binding, its pinned version, and the eval
  generating role.
- `docs/decisions/` — the new ADR.
- `docs/MODELS.md` — the row that tabulates the retired clause.
- `docs/SPEC_ROADMAP.md` — its `eval-scoring` row says what is left needs Token
  Factory, which this resolution makes false.

## Constitution Compliance

- **Principle 2 (Privacy Airlock).** This principle is what decided the change.
  The judge runs `local-only` against a local provider, so the `model_calls`
  CHECK holds by construction and nothing derived from the brain leaves the
  machine. ADR 0010 is reaffirmed rather than weakened, and the redaction
  question it would have raised does not arise because there is no egress.
- **Principle 5 (one codebase, two deployments).** The judge is configuration,
  so the judge deployment and the personal one differ by configuration and
  seeded data rather than by code.
- **Principle 7 (telemetry from line one).** The judge's model call is recorded
  by `Reasoner.complete`. No new instrumentation is owed.
- Principles 1, 3, 4 and 6 are untouched: no brain write, no night path, no
  interaction surface, and nothing outside `evals`.

## Risk

**The window.** Week 8 is 15–21 Oct. Both runs must be generated and scored with
the same judge on both sides — the curve refuses two judges as two instruments,
and since 10 Oct it also refuses two generators. Resolved on 10 Oct, which
leaves time to discover that the judge's prompt needs reworking; that discovery
needs the machine, because `ModelJudge` has only ever run against a stub.

**The grader is the weak link now, not the schedule.** A 30B model emitting five
integers against a written rubric is not the hard end of its range, but nothing
has confirmed it does so reliably. If it refuses often, the run comes back
incomplete and the curve refuses it — which is the correct behavior and still a
lost window. The first real completion on the machine is the thing to run early
rather than last.
