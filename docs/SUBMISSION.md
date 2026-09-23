# Second Shift

**An always-on assistant that turns half-formed ideas into artifacts overnight,
then interviews you in the morning about what it got stuck on.**

Built solo for the Nebius × NVIDIA Global AI Hackathon, Personal AI track.

---

## The interview is the product

Overnight agents are a commodity. Every one of them has the same failure: it
runs out of information, guesses, and hands you something confidently wrong.

Second Shift stops instead.

You capture an idea whenever you have one — a sentence, on a phone, at 2am.
Overnight, a machine you own researches it and builds something. In the morning
you open it and ask what happened. You get a briefing, and then it asks you the
questions it could not answer for itself:

> *The critic ranked the third build above the first. Keep it, or do you want
> the one that matched the brief more literally?*
>
> *Should a note that spans two topics be filed under both, or does that make
> the index useless?*

Each question carries the stage it blocked and its rationale, and **each says
whether answering it will send anything off the machine**. Your answer becomes a
tracked decision, and the next night reads it.

> Those two are from the reproducible demo, not from a real night — they
> regenerate with `--seed 42` and ship with a `[synthetic]` prefix that is
> stripped above only for readability. The real night of 16 Sep produced one
> real question; it is on the always-on machine and is somebody's actual idea,
> so it is not quoted here.

That is the whole shape: **idea in, artifact out, memory in between.** The
memory is the part that compounds, and the interview is how it gets filled by
somebody who actually knows the answer.

**A morning is never empty.** The night is a checkpointed stage machine, and
every stage that finishes commits. A build that fails at 3am still leaves you
the brief, the research and the questions — degradation is the designed
behavior, not the failure case.

---

## The privacy claim is a constraint, not a paragraph

Every idea carries a policy set at capture. `local-only` never leaves the
machine. `cloud-assisted` passes a redaction step before anything is sent.

That is enforced where it cannot be argued with:

```sql
-- This is a constraint, not a convention: violating it aborts the write.
CHECK (NOT (policy = 'local-only' AND provider IN ('token-factory','nebius-job')))
```

— `apps/api/secondshift/db/migrations/0001_initial.sql`

A code path that would send a `local-only` idea to a remote provider fails at
the database, not at a code review. Retrieval runs locally on every compute
profile; only assembled, policy-filtered context is ever eligible to leave. The
brain never leaves at all.

The table holding raw prompt and completion text says so about itself:

```sql
-- PRIVACY: this table holds raw, unredacted content for local-only ideas. It is
-- local by construction and is excluded from "export your brain" by default. It
-- must never be synced, uploaded, or included in a judge deployment.
```

Two consequences follow, and both are written down rather than assumed. A backup
of this database may never leave the boundary that holds the brain — no cloud
object store, at any price, behind any encryption (`docs/decisions/0014`). And
the API authenticates nothing and carries no version prefix, because every
consumer is same-origin on one machine for one person (`docs/decisions/0013`);
the day that stops being true, the capability with the new consumer carries the
guard on its own router.

---

## What runs on Nebius, and why that split

`docs/NEBIUS_USAGE.md` is the evidence document. The short version:

**Serverless Jobs run the build stage, fanned out to three to five parallel
variants, ranked afterward by the critic.** That is the strongest claim available
because it is the thing one DGX Spark *cannot* do. The parallelism is not a
speed-up — it is why the artifact is better, because the critic gets alternatives
to choose between instead of one draft to accept.

**Token Factory runs the research-synthesis, architect and critic turns** on
`cloud-assisted` ideas: long-context work against a quality bar where a 3B-active
local model is the wrong tool rather than a slower one.

**Everything else is local on every profile** — capture, ASR, embedding,
retrieval, redaction, the orchestrator, every database write, and all reasoning
for `local-only` ideas.

**Every model in the runtime path is an NVIDIA open model** — Nemotron 3.5
Lightning locally, Nemotron 3 Super and Ultra on Token Factory, Nemotron Speech
Streaming for ASR, Llama Nemotron Embed for retrieval, Magpie for TTS.
`docs/MODELS.md` binds each role to a checkpoint and names the ADR that chose it.

Costs are **views over recorded rows**, never stored numbers, and every view
excludes synthetic rows:

```sql
SELECT * FROM night_totals;               -- local vs cloud tokens, per night
SELECT * FROM cost_per_accepted_artifact; -- spend per artifact a person kept
```

`night_totals` is the Privacy Airlock as a chart: a `local-only` night shows
`cloud_tokens = 0`, and it shows it because no row exists rather than because a
filter hid one.

---

## What is measured, and what is not

Numbers here are from telemetry recorded at the time, with `is_synthetic = 1`
rows excluded. **Where something has not been run, this says so rather than
estimating it.**

| | Status |
|---|---|
| Capture, phone to database | **Live, taking real ideas daily** |
| Two real nights on the Spark against the live reasoner, 16 Sep | **Run.** The second completed five stages in 192 seconds, clean and distinct artifacts, one real question |
| A six-of-six night with research on, 17 Sep | **Run** |
| Redaction against the four real captured entries | **Run**, 17 Sep. Every query checked for a capitalized word, an identifier or address shape, and a four-word run from its source. None survived |
| A live Tavily search through the real code path | **Run**, 17 Sep. Five results, one credit, 1.2s; the `tool_calls` row holds the redacted query and no entry text |
| Retrieval on the machine | **Run.** 40ms index rebuild, 48 KiB index |
| The scrubber at 20× | **Measured.** 0.1ms per steady frame against a 16.7ms budget, and flat in night size |
| **A build stage fanned out to real parallel Jobs** | **Not run** |
| **A cloud night's cost beside a local one** | **Not run** |
| **The week-8 eval score** | **Not run.** The week-1 baseline is recorded and awaiting a judge |
| **The judge container built and stood up** | **Not run** |

**The unrun rows are one blocker, not four.** The Nebius credentials exist and
were verified end to end on 2 Sep — a hand-built RS256 JWT exchanged for an
access token, which then authorized a live `GET /ai/v1/jobs`. They live on the
always-on machine, outside any git-tracked path, and what is missing is a session
on that machine. `docs/SPEC_ROADMAP.md` tracks every one under *Owed
verification*.

**Nothing is stubbed to fill those rows**, and that is deliberate. A stub
executor returning plausible job results writes `model_calls` rows
indistinguishable from a real fan-out — and that fan-out is the entire evidence
for the Nebius claim. Every other stand-in in this system is visibly inert: the
echo reasoner returns its own input.

---

## The learning claim, and what would falsify it

The centerpiece is the same fixed prompts, scored in week 1 and week 8, against
one pinned rubric and two pinned brain states. If the brain learned something,
the same questions get better answers.

**The bar was fixed on 23 Sep, while nothing had been scored.** At that moment
the only eval run in the system read `judge_model = 'awaiting-scoring'`, so there
was no number to be influenced by.

An improvement is **both**, in the same direction:

1. the mean per-prompt change exceeds **twice its standard error** across the
   active prompts;
2. at least **two thirds** of them move that way.

Anything else is **"no improvement shown"** — which `config/evals/threshold.md`
is careful to distinguish from *the brain learned nothing*. Six prompts cannot
support the negative claim either.

Two things make that checkable rather than assertable. The threshold's addition
is in the history — `git log --diff-filter=A -- config/evals/threshold.md`
against the commit that records the run — and its content hash prints beside the
verdict every time:

```
  per prompt +4.17  standard error 0.83  5 of 6 agreeing
  bar: 2 standard errors and 67% agreeing, fixed 2026-09-23 (998120e365b6)

  VERDICT: improved
```

**The same arithmetic runs either way.** If it comes out the other direction,
this document will say the brain got worse, with the same prominence.

The comparison also refuses, rather than warns, in six cases where the number
would mean something other than it looks like: different rubrics, different
judges, an incomplete run, a synthetic run, different prompt sets, and — the one
that happens by accident — both runs pinning the same brain state.

---

## The failure record is part of the argument

None of this is tidied, and it is not left in by neglect.

- **Two first-party published recipes did not run on the versions they named.**
  `--moe-backend marlin` is refused for this checkpoint's mixed FP8/NVFP4 MoE,
  and `num_speculative_tokens` is rejected without an explicit method. Both are
  in `scripts/spikes/*/FINDINGS.md` with what was run instead.
- **The week-1 eval baseline was recorded five days late**, and its `week_of`
  says so rather than being tidied to day 3.
- **The first real night produced nothing usable.** Three turns ran out of
  tokens inside their deliberation and later stages copied the unfinished notes
  forward, so three stages wrote the same file. The fix, and the second night
  that worked, are both in the record.
- **`failure_ledger` is a view over a table, not a log file.** Typed failures are
  first-class rows.
- **The browser gate spent a day testing a build that did not match its
  source** — a warm bundler cache re-emitted a pre-fix chunk, and five tests
  passed against bytes nobody had written. The gate builds from clean now.
- **A drift gate was added because documents kept going stale**, and its own
  addition immediately made ten of them say "ten gates". Every count of that
  kind is now derived from the repository rather than typed.

A system that records its own failures is making a claim a polished one cannot.

---

## Check any of this yourself

A clone and no credentials is enough for all of it:

```bash
python3 scripts/gate.py
```

11 gates <!-- derived: matches scripts/gate.py ^    \(" --> — the airlock tests
first, two repository guards, a drift check, spec validation, the orchestrator
suite, web unit/types/build, a browser test against a real Chromium, and 12
mutations <!-- derived: matches scripts/check-mutations.py ^    Mutation\( -->
that reintroduce defects this project has actually shipped and require the gate
that should catch each one to fail. CI runs the same file; there is no second
definition of passing.

```bash
apps/api/.venv/bin/python -m secondshift_seed --seed 42 --db /tmp/night.db
SECOND_SHIFT_DB=/tmp/night.db SECOND_SHIFT_PROFILE=cloud SECOND_SHIFT_SYNTHETIC=1 \
  apps/api/.venv/bin/uvicorn secondshift.api.main:app --port 8080
```

The night is **deterministic by seed**, so every screenshot in this submission
regenerates from that command. Every row it writes carries `is_synthetic = 1`,
every view excludes those rows, and `scripts/check-judge-package.py` refuses to
package a database carrying unmarked rows or any `model_call_payloads` at all.

The record is in the repository: 22 capabilities
<!-- derived: count openspec/specs/*/ --> with their specifications in
`openspec/specs/`, 30 <!-- derived: count openspec/changes/archive/*/ --> archived
changes with the task lists that built them, and 14
<!-- derived: count docs/decisions/*.md --> numbered decision records, each saying
what it cost.

---

## Where to look

| | |
|---|---|
| Why the split with Nebius, and its evidence | `docs/NEBIUS_USAGE.md` |
| The principles that constrain every change | `openspec/constitution.md` |
| What is deliberately excluded, and how to override it | `NOT_BUILDING.md` |
| Numbered decisions, with their costs | `docs/decisions/` |
| What is built, what is owed, and to whom | `docs/SPEC_ROADMAP.md` |
| The falsification threshold | `config/evals/threshold.md` |
| Recovery, and which of its steps anyone has run | `docs/operations/RECOVERY.md` |
