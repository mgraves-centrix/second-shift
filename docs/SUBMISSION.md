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

> *The critic ranked the third build above the first. Keep its ranking, or the
> order they were generated in?*
>
> *Should a note that spans two topics be filed under both, or under the one it
> is mostly about?*

Each question carries the stage it blocked and its rationale, and **each says
whether answering it will send anything off the machine**. Your answer becomes a
tracked decision, and the next night reads it.

> Those two are from the reproducible demo, not from a real night — they
> regenerate with `--seed 42` and ship with a `[synthetic]` prefix that is
> stripped above only for readability. They are now verbatim from
> `packages/seed/secondshift_seed/content.py`; until 16 Oct both second clauses
> were paraphrased, so running the seed produced different text than this
> document showed inside quotation marks. The real night of 16 Sep produced one
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

**On 10 Oct it overruled a decision this project had already made.** ADR 0006
bound the eval judge to a cloud model on 27 Aug. ADR 0010 then decided, on
2 Sep, that brain topic files carry `local-only`, with the reasoning that a file
distilled from `local-only` material inherits the restriction — "treating the
output as less restricted than its most restricted input would launder the
policy." An eval answer is generated from those files. So the cloud judge had
been impermissible for five weeks, and nobody had noticed, because nothing in
the system had ever scored anything: a dead clause is never executed, so it
never fails.

`docs/decisions/0015` retires it. The judge is the local reasoner, and the
policy is a constant in the code rather than configuration, because a value
that could be set to `cloud-assisted` is the switch 0010 refused to build.
**That is the difference between a constraint and a paragraph** — it cost the
better instrument, a 550B grader traded for a 30B one, and the trade is recorded
with what it cost rather than argued away.

---

## What runs on Nebius, and why that split

`docs/NEBIUS_USAGE.md` is the evidence document. **This section separates the
split as decided from the split as exercised, because they are not the same and
the measured table below says so.**

### Decided, and not yet exercised

**Serverless Jobs are to run the build stage, fanned out to three to five
parallel variants, ranked afterward by the critic** (`docs/decisions/0004`).
That is the strongest claim available because it is the thing one DGX Spark
*cannot* do, and the parallelism is not a speed-up — it is why the artifact
would be better, because the critic gets alternatives to choose between instead
of one draft to accept.

**It has not run.** `openspec/changes/2026-09-02-add-nebius-executor/` stands at
11 of 23 tasks. Built since 17 Oct: the poller's half, which collects a job's
report of what it did and records it exactly once however often it is collected,
and refuses to present a job whose report never came as one that cost nothing.
Not built: dispatch. A job runs on Nebius, so to reason it needs a Token Factory
key there, in Nebius's secret store — and whether a key may live anywhere but
the always-on machine is a decision for the subject, not one this document or
its author makes by convenience. The credential itself was verified end to end
on 2 Sep: a hand-built RS256 JWT exchanged for a real access token, which then
authorized `GET /ai/v1/jobs` with a 200 and an empty list.

**Token Factory is to run the research-synthesis, architect and critic turns**
on `cloud-assisted` ideas: long-context work against a quality bar where a
3B-active local model is the wrong tool rather than a slower one. **The cloud
reasoner exists and answered a real call from the machine on 17 Oct**, recorded
with its cost. That call found the rate table keyed by console display names the
API rejects with a 404, and reasoning tokens — billed as output — unpriced; both
are fixed, and the rates were re-read from the API's own `/v1/models`. **No idea
is sent to it.** The privacy-airlock spec requires a `cloud-assisted` turn to
leave as redacted, policy-filtered context, and neither the redaction of a
reasoning prompt nor that assembly exists, so the night refuses the cloud
profile. And on 10 Oct `docs/decisions/0015` found that brain-derived text cannot
reach a remote provider at all, so the eval judge that was bound to Token Factory
is now local.

**Nothing is stubbed to close either gap**, and that is the deliberate part. A
stub executor returning plausible job results writes `model_calls` rows
indistinguishable from a real fan-out — and that fan-out is the entire evidence
for the claim. Every other stand-in here is visibly inert: the echo reasoner
returns its own input.

### Running now

**Everything else is local, on every profile** — capture, embedding, retrieval,
redaction, the orchestrator, every database write, and all reasoning for
`local-only` ideas. Two real nights ran against the live local reasoner on
16 Sep and a six-of-six night with research on 17 Sep.

ASR and TTS are in neither list: the speech spike has not run and no
`Transcriber` is implemented. Text capture has been live since 28 Aug, so voice
gates nothing — but it is not in the runtime path, and the model list below is
what each role is *bound* to rather than what each has done.

**Every model bound to a role is an NVIDIA open model, and no third-party LLM
appears anywhere in the runtime path** — Nemotron 3.5 Lightning locally,
Nemotron 3 Super and Ultra on Token Factory, Nemotron Speech Streaming for ASR,
Llama Nemotron Embed for retrieval, Magpie for TTS. `docs/MODELS.md` binds each
role to a checkpoint and names the ADR that chose it. Of those, the ones that
have actually produced output are Lightning and the embedder; Magpie's spike
passed on 28 Aug without being wired in.

Costs are **views over recorded rows**, never stored numbers, and the exclusion
of generated data is on the run — `run_cost` carries `WHERE r.is_synthetic = 0`
and `night_totals` is built on it, so neither can report a seeded night:

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
| Capture, phone to database | **Live since 28 Aug.** Four real entries by 17 Sep, which is the number the redaction row below checked against; the count since is in the database on that machine |
| Two real nights on the Spark against the live reasoner, 16 Sep | **Run.** The second completed five stages in 192 seconds, clean and distinct artifacts, one real question |
| A six-of-six night with research on, 17 Sep | **Run** |
| Redaction against the four real captured entries | **Run**, 17 Sep. Every query checked for a capitalized word, an identifier or address shape, and a four-word run from its source. None survived |
| A live Tavily search through the real code path | **Run**, 17 Sep. Five results, one credit, 1.2s; the `tool_calls` row holds the redacted query and no entry text |
| Retrieval on the machine | **Run.** 40ms index rebuild, 48 KiB index |
| The scrubber at 20× | **Measured.** 0.1ms per steady frame against a 16.7ms budget, and flat in night size |
| **A build stage fanned out to real parallel Jobs** | **Not run** |
| **A cloud night's cost beside a local one** | **Not run.** One real Token Factory call, 17 Oct, reads correctly off `night_totals`; no night may send an idea to the cloud until redaction exists |
| **The week-8 eval score** | **Not run.** Week 8 is 15–21 Oct. The judge ran against the real checkpoint on 16–17 Oct and found a defect in itself: its reader refused two valid judgements, misled by malformed drafts earlier in the same completions. Fixed and pinned into the judge's version; re-read over every kept completion, no other score moved. What remains is an answer that sometimes runs to the token limit, which leaves a run incomplete |
| **The judge container built and stood up** | **Run**, 16 Oct on the machine and 17 Oct for amd64, ADR 0009's target. The seed and the package check ran inside the build; the container served `/health` and the honest capability report. Not yet read by somebody who has not seen it |

**The rows still unrun are four different blockers, and this document claimed
one until 16 Oct.** It read "one blocker, not four — and it is a credential, not a
machine", which was written on 10 Oct and contradicted by a decision made the
same day. Separating them:

| Unrun row | What it waits on |
|---|---|
| The parallel Jobs fan-out | **A decision on a Token Factory key inside Nebius**, then the dispatch client |
| The cost comparison | **Prompt redaction and policy-filtered context assembly**, which the privacy-airlock spec requires and nothing implements |
| The week-8 eval score | **A decision on retrying a sample whose answer never finished.** At the rate observed, an 18-sample run with no such sample is not the likely outcome, and an incomplete week 1 cannot be retaken |
| A real night revising a belief | **An idea queued from the phone** |

The Nebius credentials exist and were verified end to end on 2 Sep: a hand-built
RS256 JWT exchanged for an access token, which then authorized a live
`GET /ai/v1/jobs`. They live on the always-on machine, outside any git-tracked
path. Both endpoints answer from anywhere —
`api.studio.nebius.com/v1/models` returns 401, a missing key rather than a
missing route — so where a key may live is a decision rather than a fact about
the network. `docs/SPEC_ROADMAP.md` tracks every unrun row under *Owed
verification*.

Nothing is stubbed to fill them, for the reason given above: a plausible job
result is indistinguishable from a real one once it is a row.

---

## The learning claim, and what would falsify it

The interview is the product; this is how one claim inside it gets checked.
*It gets better at being me* is the claim, and the check is the same fixed
prompts scored in week 1 and week 8 against one pinned rubric and two pinned
brain states. If the brain learned something, the same questions get better
answers.

**As of 16 Oct that comparison has not been run.** The week-1 baseline is
recorded and the only eval run in the system still reads
`judge_model = 'awaiting-scoring'`. Week 8 is 15–21 Oct, and running it needs a
session on the always-on machine, where the model, the database and the brain
are. What follows is therefore about the apparatus, not about a result — and the
apparatus is the part worth reading, because it was built to make the result
hard to fake before there was a result to fake.

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
verdict every time, so a bar edited after the fact is visible in the output
rather than only in the history.

The verdict's shape, **with invented numbers, because there is no result yet**:

```
  per prompt <mean>  standard error <se>  <k> of <n> agreeing
  bar: 2 standard errors and 67% agreeing, fixed 2026-09-23 (998120e365b6)

  VERDICT: <improved | regressed | no improvement shown>
```

The hash is real and checkable today: `sha256sum config/evals/threshold.md`.
The numbers are placeholders on purpose. An earlier draft of this document put
plausible figures there — `+4.17`, `5 of 6`, `improved` — and nothing marked
them as an illustration. In a section about a measurement that has not run, a
number in a monospace block is something a reader can quote. That is the same
defect as the seeded demo questions this document used to present as the
product's output, found the same way: by re-reading our own claims against what
had actually happened.

**The same arithmetic runs either way.** If it comes out the other direction,
this document will say the brain got worse, with the same prominence. And if it
does not run before the deadline, this section will say that, which is what it
says now.

The comparison also refuses, rather than warns, in 11 <!-- derived: matches apps/api/secondshift/evals/runner.py raise NotComparable\( --> cases where the
number would mean something other than it looks like: different rubrics,
different judges, a run never scored, a run scored incompletely, a synthetic
run, different prompt sets, both runs pinning the same brain state — the one
that happens by accident — and the three added on 10 Oct, which are the ones the
shortest path to a week-8 number would have hit: **a run that does not record
which model produced its outputs, two runs whose outputs came from different
models, and two runs whose outputs came from different agent prompts.** A week 1
generated on the Spark and a week 8 generated in the cloud is a difference in
the model; a role prompt edited in between is a difference in the prompt. This
document would have called either one learning.

The eleventh was added on 17 Oct, after the first real scoring found the judge
refusing some of its own output: **one judge model asked two different ways.**
The judge's prompt was pinned by nothing and the curve compared judges by name,
so fixing that prompt between week 1 and week 8 would have passed every check
above. A judge's recorded version now carries the hash of what it was asked.

That figure derives from the refusals in the code rather than being typed here.
Three documents disagreed about it — five, six, and the truth — for the three
weeks before anyone read them side by side.

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
- **Three of those derived counts were checked by nothing, in this file.** A
  marker binds to the nearest number on its own line; a paragraph reflow had
  left three figures one line up, so the gate matched nothing and reported the
  document clean. Two were stale. The bullet above was therefore true in
  intent and false in fact for weeks, which is the exact shape it describes.
  An unbound marker is now a failure rather than a skip.
- **This document showed a verdict with invented numbers.** A monospace block
  gave `+4.17`, `5 of 6`, `improved` for a measurement that has never run, with
  nothing marking it as an illustration. It now shows the shape with
  placeholders.
- **And it paraphrased its own demo inside quotation marks.** Both questions
  quoted above had invented second clauses, in a passage telling the reader they
  regenerate from `--seed 42`. They are verbatim now.

A system that records its own failures is making a claim a polished one cannot.
Three of the bullets above were found on 16 Oct by reading this file against the
code it describes — which is the practice the claim actually rests on, and the
reason the list keeps growing after the mechanisms are in place.

---

## Check any of this yourself

**No credentials, and no access to the always-on machine.** A bootstrap first,
though — Python 3.12, Node, and a Chrome the browser test can drive:

```bash
python3 -m venv apps/api/.venv
apps/api/.venv/bin/pip install -c apps/api/constraints.txt -e "apps/api[dev]" -e packages/seed
npm --prefix apps/web ci
npm install --global @fission-ai/openspec@1.11.0
python3 scripts/gate.py
```

That is `docs/development/GATES.md`'s clean-clone section, repeated here because
this document said "a clone and no credentials is enough" and the gate's first
act is to refuse: *no interpreter at `apps/api/.venv/bin/python`*. It says which
and why, which is the behavior wanted, but it is not what the sentence promised.

11 gates <!-- derived: matches scripts/gate.py ^    \(" --> — the airlock tests
first, two repository guards, a drift check, spec validation, the orchestrator
suite, web unit/types/build, a browser test against a real Chromium, and 20 mutations <!-- derived: matches scripts/check-mutations.py ^    Mutation\( -->
that reintroduce defects this project has actually shipped and require the gate
that should catch each one to fail. CI runs the same file; there is no second
definition of passing.

```bash
apps/api/.venv/bin/python -m secondshift_seed --seed 42 --db /tmp/night.db
SECOND_SHIFT_DB=/tmp/night.db SECOND_SHIFT_PROFILE=cloud SECOND_SHIFT_SYNTHETIC=1 \
  apps/api/.venv/bin/uvicorn secondshift.api.main:app --port 8080
```

The night is **deterministic by seed**, so the night this document describes is
the one that command produces — the same 1,232 events, the same stages, the same
questions. This file carries no images; the repository has none. Any screenshot
shown alongside the submission regenerates from that seed rather than being a
picture of a state nobody else can reach, which is the only property worth
claiming here.

Every row it writes carries `is_synthetic = 1`, every view excludes those rows,
and `scripts/check-judge-package.py` refuses to package a database carrying
unmarked rows in an evidence table or any `model_call_payloads` at all.

The record is in the repository: 22 capabilities <!-- derived: count openspec/specs/*/ -->
with their specifications in `openspec/specs/`,
33 <!-- derived: count openspec/changes/archive/*/ --> archived changes with the
task lists that built them, and 15 <!-- derived: count docs/decisions/*.md -->
numbered decision records, each saying what it cost.

**Three of those figures were checked by nothing until 16 Oct.** A derived
marker binds to the nearest number on its own line, and a paragraph reflow had
left three of them with the figure on the line above — so the drift gate matched
nothing, reported nothing, and called this document clean. Two were stale: the
mutation count read 12 against 19, and the decision count 14 against 15. The
gate now treats a marker that binds to nothing as a failure rather than a skip,
which is the rule `scripts/check-mutations.py` already applied to its own stale
anchors.

**It then demonstrated itself inside the hour.** Binding those markers was worth
a mutation of its own, which moved the mutation count to 20 — and the
newly-bound marker failed the gate on the figure that had been corrected minutes
earlier. The number above is 20 because a check caught it, not because anybody
remembered.

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
