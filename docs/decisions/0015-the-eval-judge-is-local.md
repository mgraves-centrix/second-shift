# 0015 — The eval judge is local, because 0010 already said so

**Status:** accepted · **Date:** 2026-10-10
**Supersedes the eval-judge clause of [0006](0006-model-bindings.md).** The rest
of 0006 stands unchanged. **Reaffirms [0010](0010-brain-content-carries-local-only.md).**

## Context

Two accepted ADRs have contradicted each other since 2 September, and nobody
noticed for five weeks.

ADR 0006, on 27 August, bound the eval judge to the cloud:

> Nemotron 3 Ultra 550B A55B for frontier turns and as the version-pinned eval
> judge

ADR 0010, on 2 September, decided that brain topic files carry `local-only`, and
its rationale is explicit that the restriction travels rather than stopping at
the file:

> A file distilled from local-only material inherits local-only. [...] Treating
> the output as less restricted than its most restricted input would launder the
> policy.

An eval run generates its answers from the brain at a pinned commit —
`EvalRunner.score` reads `BrainRepo.topic_files_at`, which returns exactly the
files 0010 is about. So an eval output is distilled from `local-only` material
and inherits that policy by 0010's own argument. The constitution then forbids a
`local-only` idea reaching a remote provider, enforces it as a `CHECK` on
`model_calls`, and says proposals must not weaken, bypass or make it
conditional.

0006's clause has therefore been impermissible since the day 0010 was accepted.

**It survived because nothing had ever been scored.** No implementation of the
`Judge` protocol called a model until 10 October; the only implementation was a
stub returning arithmetic on the length of its input, `EvalRunner.score` was
reachable from nowhere but the test suite, and the one recorded eval run reads
`judge_model = 'awaiting-scoring'`. A dead clause is never executed, so it never
fails. The disagreement was found by reading the record before implementing
against it, not by anything in the repository noticing.

## Decision

**The eval judge is the local reasoner, and its calls run `local-only`.**

The judge drives the `Reasoner` interface rather than a provider, so which model
grades is configuration — `evals.judge_version` and `evals.generating_role` in
`config/models.toml`. The policy is not configuration: `evals/__main__.py` holds
it as a constant, because a value that could be set to `cloud-assisted` is the
switch 0010 refused to build.

**Generation goes through the agent path**, with the eval prompt as the task and
the brain's topic files as context. An answer produced by a composition written
for evaluation measures that composition, and an improvement in it cannot be
attributed to the product without a further argument nobody has made.

**Moving the judge to a remote provider requires a new ADR superseding 0010**,
with the argument 0010 asks for. It is not a configuration change, and this
decision does not leave a flag that would make it one.

## Rationale

**The airlock decided it, not the schedule.** A local judge also takes the
Nebius credential off the critical path with the week-8 window opening 15
October, and the curve compares differences under a pinned judge rather than
absolute scores, so a consistent grader is what the measurement needs. Those
were the reasons offered before 0010's conflict was found. They are now the
secondary ones; recording them as primary would leave the next reader thinking a
cloud judge is a trade-off away rather than forbidden.

**The pinned version is configuration and not read from the endpoint.** vLLM
reports whatever `--served-model-name` was set to at launch, so a version taken
from the server changes when the server is restarted against another checkpoint
— and a past run's claim about itself would then depend on the present.

## Consequences

**A 550B grader is given up for a 30B one.** The claim under measurement is a
difference across two pinned brain states under one pinned judge, so the loss
falls on the absolute level of the scores rather than on the comparison. It is
still a loss and it is not being argued away: nothing has yet confirmed that the
local model emits five integers against a written rubric reliably, and a judge
that refuses often leaves the run incomplete, which the curve refuses. The first
real completion on the machine is the thing to run early.

**`docs/MODELS.md` is corrected, not rewritten.** Its cloud table tabulated
0006's clause; the row now says the clause is retired and points here.

**The curve gained two refusals because of this decision.** Generating through
the agent path reintroduced, one layer up, the hole that
`2026-10-10-a-score-knows-which-model-produced-it` had just closed: a role
prompt is versioned, `eval_runs` pins no prompt, and `distiller` was already at
v2. The comparison now refuses two runs whose agent prompts differ, read through
`eval_results.model_call_id` → `model_calls.agent_invocation_id` →
`agent_invocations.agent_id` → `agents.prompt_sha`. No migration: every link
already existed.

**A deployment can no longer score the other kind of run.** Making scoring
reachable exposed that `is_synthetic` marks results while the curve's exclusion
filters runs — two different tables — so a judge deployment scoring a run
recorded as real would write synthetic results that `summarize` reads as that
run's scores. The runner refuses it now.

## Alternatives considered

**Keep 0006's clause and supersede 0010.** The only path that preserves the
better instrument, and it trades away the airlock's strongest guarantee: that a
`local-only` idea cannot reach a remote provider, enforced by the database
rather than by review. The eval outputs are the most personal text this system
produces — the prompt set includes one that asks for a README in the subject's
voice and one about what they have been avoiding — so this is the worst place to
spend that guarantee, not the easiest.

**Defer: grade locally for these runs, leave 0006 standing.** Rejected because
it describes a schedule constraint, and what is actually true is a prohibition.
A deferral would have left 0006 readable as current and the next reader one
configuration change from crossing principle 2.
