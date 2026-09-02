# Spec Roadmap

What gets specified next, in the order the work unblocks. One OpenSpec change
per capability unless noted.

Shipped, in the order they landed: `persistence`, `telemetry`,
`compute-profiles`, `privacy-airlock` (`2026-08-27-add-foundations`, and
`2026-08-27-fix-probe-model-identity`), then `capture`, `brain`, `evals`,
`synthetic-seed`, `local-inference`, `night-timeline`, `retrieval` and
`agents`.

**Do not trust that list to be current — run `openspec list --specs`.** It said
"ten capabilities across nine changes" while its own body said twelve, because
the header was written once and the body was appended to. The count and the
archive are both derivable in a second; a number typed here is a number that
goes stale the next time something ships.

Each entry lists what is **already decided** — so the proposal has material to
draw on rather than re-deriving it — and what is **still open**, which becomes
`[NEEDS CLARIFICATION]` markers rather than assumptions. Headings are marked
shipped as they land; an entry still carrying an **Open** line is one nobody has
answered yet.

---

## Resolved 2026-08-27

- **Eval baseline is split.** Day 3 records prompts, `rubric_sha` and
  `brain_sha`; scoring runs day 5 once a judge exists. Detail below.
- **Geolocation: configured home, per-entry override.** Home lat/long in config
  keeps capture frictionless; an explicit override covers capture while
  traveling. No browser geolocation prompt.
- **Brain layout: stable topic files plus a dated journal.** Detail below.
- **Offline replay dedup** uses the client-generated ULID as an idempotency
  key. The client already needs an id to queue an entry offline.
- **Titles are derived, not entered.** Typing a title is friction on the one
  interaction that must stay frictionless.
- **Repository is public** as of 2026-08-27, Apache 2.0, history audited first.

---

## The eval sequencing problem, and its resolution

**The day-3 eval baseline has no judge.** `docs/WEEK_ONE.md` puts the week-1
eval baseline on day 3, but the local reasoner does not exist until day 4 and
Token Factory is not verified until day 5. On day 3 there is no model to
generate outputs and none to score them.

The week-1-versus-week-8 comparison is the submission's centerpiece, so this
cannot silently slip. Two workable shapes:

- **Split the baseline.** Day 3 records the fixed prompts, the rubric SHA and
  the brain SHA — the things that must be captured *at that moment* and cannot
  be reconstructed later. Scoring runs on day 5 against the recorded brain
  state. The `eval_runs` schema already separates `brain_sha` from
  `judge_model`, so this needs no schema change.
- **Move the baseline to day 5.** Simpler, but the brain has then absorbed two
  more days of dogfooding, so "week 1" measures a slightly later brain.

**Resolved: split the baseline.**

Day 3 records only what cannot be reconstructed later — the fixed prompt set,
the `rubric_sha`, and the `brain_sha` of a two-day-old brain. No model is
required for that. (In the event day 3 recorded nothing; the baseline was written
on 2 Sep against the brain it actually had. See the `evals` entry.) Day 5 generates and scores against that recorded brain
state, once Token Factory is verified.

`eval_runs` already separates `brain_sha` from `judge_model`, so this needs no
schema change. What it does need is for the day-5 scoring run to be pinned to
the day-3 `brain_sha` rather than to whatever HEAD is by then — that is the
whole point, and it is the one thing that can silently go wrong.

---

## Week one

### 1. `capture` — shipped 28 Aug

Entries from the PWA to a logged row. Everything downstream waits on it, and
day-3 dogfooding starts the memory clock that cannot be restarted.

**Decided:** entry schema and timezone fields; text-first with voice layered
later; policy selected at capture; unavailable policies shown disabled with
their specific reason (never hidden); offline-tolerant queue.

**Also decided:** home lat/long in config with a per-entry override; offline
replay deduplicated on the client-generated ULID; titles derived rather than
entered.

**Resolved and shipped.** The surface shows a persistent *count* of entries
captured and not yet acknowledged, and nothing per-item. A count is enough to
stop a re-tap; a list is not, because a per-item surface is what a retry, edit
or delete control attaches to, and `NOT_BUILDING.md` excludes task management.
The count clears on drain without user action.

### 2. `brain` — shipped 28 Aug

The plaintext memory: a sibling git repository the orchestrator reads and
commits to.

**Decided:** ADR 0001 — separate repository, not a subdirectory or submodule;
human-readable markdown; `runs.brain_sha` pins state per run.

**Also decided:** stable topic files — `profile.md`, `style-guide.md`,
`skills/*.md` — rewritten in place as the system learns, alongside a dated
append-only journal for raw history. The eight-week diff is read off the topic
files: a diff of an append-only log is just more stuff, while a diff of an
edited belief file *is* the learning claim, visible.

**Resolved and shipped.** One commit per sync batch. Sync stages `journal/`
rather than the tree, so a hand-edited topic file is never swept into an
automated commit. Local-only, no remote, mirrored to a NAS.

**The brain lives on the always-on machine**, beside the database the
orchestrator writes — not on the development laptop. ADR 0001 said "sibling
repository" and left the machine implicit; sync has no brain to write to if the
two are on different hosts, which only became obvious when sync first ran. Edit
topic files there, or clone and push back.

**Still open:** what the topic files should contain, which is a question for
their subject rather than for the code. The seeded profile is explicitly a
sketch asking to be corrected.

### 3. `evals` — shipped 28 Aug

The measurement spine. Run 1 must exist early or the week-8 comparison has no
left-hand side.

**Decided:** schema exists; judge model and rubric SHA are pinned per run;
repeated sampling gives variance rather than a point estimate.

**Shipped: the machinery, deliberately without the content.** The runner, the
scoring path, repeated sampling, and the `eval_runs` / `eval_results` writes,
with the prompts left as data so choosing them is data entry rather than a code
change. Rubric v1 is committed at `config/evals/rubric.md` and hashed by content
rather than by the commit that touched it. The sequencing question above is
resolved.

**Which prompts are held out is database state, not repository state.** The ten
candidates live in `config/evals/candidates.md`; the selection is
`eval_prompts.active`, set by `python -m secondshift.evals activate <slug>` and
read back by `python -m secondshift.evals status`. It lives beside the database
on the always-on machine, so **a clone cannot show it** — do not read an
unmarked `candidates.md` as an unmade decision.

**The week-1 baseline does not exist.** Read directly from the always-on machine
on 2 Sep over the tailnet: `eval_runs` holds **zero rows**. An earlier note in
this file said one row was awaiting scoring and that the day-3 gate was met.
That was wrong, and it was load-bearing — the next session was told not to
re-open the gate.

`docs/WEEK_ONE.md` states the day-3 pass gate as "an `eval_runs` row exists
pinning `rubric_sha` and the day-3 `brain_sha`." No such row was ever written.

What the machine actually holds, all of it verified read-only:

| | |
|---|---|
| `eval_runs` | **0 rows** — no baseline, nothing pinned |
| `eval_prompts` | 10 loaded, **6 active** — not the five recorded here |
| `entries` | 4 real captures, one archived and three still queued |
| `runs` | 0 — no night has ever executed |

The prompts were loaded and activated on **30 Aug**. `seed` and `activate` ran;
`baseline` never did. Two commands of the three.

**There is no rubric drift, and there never was.** The rubric on the machine is
byte-identical to the committed one — both hash to
`b4decd6fe7748e26afca39c267d7725c6bbde0d753c1f4071ae16c390670c563`. The
`4a7c2e91b3d0` this file previously reported matches no file on that machine, and
with `eval_runs` empty there was no pinned value for it to disagree with either.
Where that figure came from is unknown; it did not come from this rubric.

So the question this entry spent a week framing — which of two hashes the
baseline pinned — had no answer because it had no baseline. The reconciliation
work still stands on its own: `status` now reports recorded runs rather than
echoing the hash of the file it just read, and against this database it says
"no recorded run has pinned it yet," which is the true state and the thing
nobody could see before.

**The clock that could not be restarted was never started.** Every day it stays
unrecorded, "week 1" pins a later brain — the journal already runs through 28 Aug
and the brain has committed since. Recording it now is cheap and gets less
honest daily; recording it never makes the week-8 comparison impossible.

**Both decisions taken, 2 Sep, and the baseline is now recorded.**

```
01M1FYFECEXC5ZJEWHNP7WZMXB  week_of 2026-08-31  rubric b4decd6fe774
                            brain ad17b3bcddb6  awaiting-scoring
```

`week_of` is the Monday of the week it was actually recorded, not of the week it
was meant to be. The run pins the brain it genuinely measured — `ad17b3b`, five
days past day 3 — so the lateness is visible in the data rather than papered over
by a label. Recorded as `mgraves`, not as root: the database and both user
services are owned by that account, and a root-owned WAL file would have broken
them silently.

**The held-out set is six, not five.** The number five in this plan was never a
requirement, only an expectation; six prompts were activated on 30 Aug and six is
what the baseline pins. `agent-memory-systems`, `been-avoiding`,
`every-metric-dashboard`, `file-naming`, `readme-in-my-voice`, `shorter-briefing`.

**Still open:** scoring, which needs a judge and a generating provider — that is
`local-inference` and `nebius-executor`, not this capability.

**The instrument now exists** — `2026-09-02-reconcile-rubric-pinning`. `status`
reports every recorded run's pinned `rubric_sha` and `brain_sha` beside the hash
of the file on disk, says so plainly when they disagree, and exits non-zero. On
the always-on machine, this now answers the question:

```bash
python -m secondshift.evals status
```

Two guards close behind it. `score` compares the rubric it was handed against the
run's pinned hash before generating anything and refuses on a mismatch, so week 1
cannot be graded against a rubric it never used. And `deploy.sh` hashes the
target's rubric before the `rm -rf` and refuses to replace one that differs — an
edit made only on the machine was previously destroyed by the next deploy, which
would have changed the rubric out from under a pinned baseline with nothing
surfacing it. The rubric's own opening line is the rule: never edit in place;
supersede with `rubric-v2.md`.

~~**Still open:** which value the baseline actually pinned, and whether to
re-record week 1.~~ **Closed by the paragraphs above, which this line survived
by being written before them.** There was never a competing hash: the rubric on
the machine is byte-identical to the committed one, `4a7c2e91b3d0` matches no
file anywhere, and the baseline recorded on 2 Sep pins `b4decd6fe774`. Nothing
is left to decide, and a reader arriving here first would have re-opened a
question the same document already answered twice.

### 4. `local-inference` — shipped 2 Sep

vLLM serving Nemotron 3.5 Lightning, implementing `Reasoner` against the
existing interface.

**Decided:** model bindings in ADR 0006 and `docs/MODELS.md`; NVFP4 with DSpark
speculative decoding; the base class already owns telemetry, so this
implements `_do_complete` only.

**Resolved by Spike B, 27 Aug** — the configuration question, not the
capability. NVFP4 at `--gpu-memory-utilization 0.30` with a 65k context limit
holds 43 GiB and leaves 77 free, and is *faster* at 3 concurrent than the
recommended 0.85, which consumed 112 of 121 GiB and left no room for ASR or the
embedder. Co-residency is therefore answered for the reasoner; MagpieTTS adds
1.85 GiB on top (Spike C), and ASR is unmeasured. Full detail in
`scripts/spikes/spike-b-local-inference/FINDINGS.md`.

**Shipped.** `VllmReasoner` implements `_do_complete` over the OpenAI-compatible
endpoint with the standard library, and the registry binds it on every local
profile — `cloud` keeps the placeholder, which is `nebius-executor`'s. A local
profile with no served-model name configured is now refused rather than quietly
echoed, because a registry that substitutes a placeholder for a missing backend
is what produced a system that answered without a model.

Both carried-over items are handled. The served model's visible chain-of-thought
is read from `reasoning_content` where vLLM's parser separates it and returned
whole where it does not — no marker-string splitter, which would delete the
answer whenever it guessed wrong. And `deploy/spark/second-shift-reasoner.service`
supervises the container, restarts it, and publishes it on 8200 rather than the
contested 8000 the spike served on.

Two telemetry gaps closed with it, both only reachable once a backend could fail:
a call whose backend raised recorded nothing at all, and a completion truncated
at the token limit was indistinguishable from a finished one.

**Not verified from a development window.** No call has reached the real server —
the provider is exercised against a stub speaking the endpoint's documented
shape, and the units are checked for agreement with `config/models.toml` rather
than started. The first real completion on the machine is where the remaining
risk sits.

### 5. `nebius-executor` — day 5

**Carries every obligation deferred out of day 1. These are written down here
because a deferred obligation with no home is a dropped one.**

- The authenticated telemetry ingest endpoint. The recorder-side contract
  exists and is tested; the transport does not.
- **Reachable from Nebius without exposing the machine that holds the brain to
  the public internet.** Joining the job to the tailnet is the intended route;
  a public endpoint widens the attack surface on the always-on machine and
  needs an explicit decision before it is built.
- Ingest must serialize through the orchestrator's writer, never a second
  connection.
- ~~Per-token rates for Lightning and Ultra in `config/pricing.toml`.~~
  **Resolved 27 Aug, hours after this entry was written.** Lightning, Super and
  Ultra were all read from the Token Factory console for `eu-north1`, standard
  and Batch, and are in `config/pricing.toml`. That supersedes both problems
  this bullet described: the blended figures never had to be split, and Super no
  longer rests on a third-party aggregator. The Batch rows are exactly half of
  standard, matching the tariff structure recorded below. A rate that is missing
  still fails loudly — none is missing today.
- Resolution of the judge deployment target.

**Decided:** ADR 0004 — build stage fans out to parallel variants, one job each;
`Executor.dispatch` carries the telemetry descriptor; `JobResult` never carries
telemetry.

**Proposed 2 Sep, not implemented.** `2026-09-02-add-nebius-executor` carries the
proposal, the design and the delta spec. No Nebius credential exists in a
development window, and nothing is stubbed: a stub executor returning plausible
job results would be indistinguishable in `model_calls` from the real fan-out
that is the whole evidence for the Nebius argument.

**All four markers resolved 2 Sep**, and none by assumption.

- *The judge deployment target* — a Serverless AI Endpoint on a no-GPU
  container VM. ADR 0009, which closes ADR 0004's open risk in the opposite
  direction to the one it anticipated: Endpoints host arbitrary containers.
- *How a job reaches the machine holding the brain* — it does not. The job
  reports nothing and `await_result` collects its telemetry, so no inbound path
  exists to secure and no credential sits inside an ephemeral job.
- *Idempotency on a double report* — a client-generated key per row, enforced
  by `UNIQUE (dispatching_invocation_id, local_id)` in the recorder, mirroring
  the ULID replay path `capture` already uses.
- *Batch for Lightning and Super* — **unavailable**, established by reading the
  account rather than the docs. `us-central1` serves no `/v1/batches` route at
  all, and creation on the unregioned host returns 403 "temporarily
  unavailable". Night reasoning runs on the standard API; the 50% saving stays
  hypothetical. The modeling is settled regardless: a batch turn is an
  `Executor` job, never a `Reasoner` that polls behind a synchronous signature.

#### Pricing structure observed in the Token Factory console, 2026-08-27

Nemotron rows were not in the captured extract, but the tariff structure is
consistent enough across the eleven models that were to be worth designing
against.

- **Batch is exactly 50% of standard**, input and output, across every model
  observed — DeepSeek R1/V3/V3.2/V4, Devstral, Cosmos3, even FLUX per-image.
  Zero exceptions.
- **`-fast` variants cost roughly 2.5x standard** (DeepSeek-R1 $0.80/$2.40
  against fast at $2.00/$6.00).
- **Output is consistently 2-3x input.** Completion-heavy stages dominate cost,
  so a verbose critic is expensive in a way a long prompt is not.
- Region is `eu-north1`. Every cloud call crosses the Atlantic from the Spark.
- **Dedicated endpoints bill by GPU hour**: H100 $4.05, H200 $4.70, B200 $7.40,
  B300 $8.10, L40S $2.00. This is a real answer to the judge-hosting question —
  a dedicated endpoint is rentable by the hour rather than requiring a serverless
  app target.

**The design consequence: the night pipeline should use the Batch API.**
Overnight work is the definition of batchable — nothing waits on a 2am run, and
the trans-Atlantic latency that would make batching painful for interactive work
is irrelevant when the deadline is morning. If Nemotron follows the observed
tariff, this halves cloud spend on every night, and cost per accepted artifact
is a scored chart.

The morning interview is the exception and must stay on the standard API: a
person is waiting.

This needs confirming for Nemotron specifically before it is built on, and it
changes what `Executor` and the cloud `Reasoner` look like — a batch submission
is submit-then-poll, not request-response.

### 6. `synthetic-seed` — shipped 28 Aug

The night generator. Unblocks all frontend work and seeds the judge instance.

**Decided:** every row carries `is_synthetic = 1`; rollup views already exclude
it; a full night is roughly six hours and 400+ events across lanes.

**Shipped and measured.** `python -m secondshift_seed --seed 42` writes one
run of 1,223 events over 7.3 hours across 7 lanes, 182 invocations at depth 3,
362 model calls with costs and latencies, and 6 failures. 1,019 events carry
`duration_ms` and render as bars; the rest are ticks. Every row is
`is_synthetic = 1` and the rollup views exclude them. Deterministic by seed, so
a screenshot is reproducible.

**Still open:** how realistic the generated *content* must be to be worth
screenshotting. The shape is dense enough to build against; whether the prose
inside an artifact survives a judge reading it closely is unanswered, and is a
question for `night-timeline` to raise once something renders it.

### 7. `night-timeline` — shipped 2 Sep

The playback contract behind the scrubber. Built once, used three times.

**Decided:** `events` carries pre-rendered scalar columns so rendering never
parses JSON; `duration_ms` non-null renders as a bar, null as a tick.

**Both open questions closed by measurement, not preference.** There is no
windowed query: the whole night is one response, because a window would put a
fetch in the middle of a drag. And the tree does not collapse at the depth this
system produces — three offsets inside a 30px lane are distinguishable, and
Spike D's numbers say the rendering is nowhere near its budget.

**Spike D chose DOM.** Incremental DOM holds 0.1ms per steady frame against a
16.7ms budget, and its cost is flat in night size where canvas's is linear —
canvas is the approach that degrades as nights get denser, which inverts the
intuition the abort criterion in `docs/WEEK_ONE.md` was written on. Full detail
in `scripts/spikes/spike-d-scrubber-rendering/FINDINGS.md`.

**Four things the data corrected**, each of which would otherwise have shipped
quietly. The frame ends where the last event *ends* — the longest bar begins 67
minutes before the last event starts. Stages travel with the night because
`runs.outcome` is null on every recorded run: **nothing calls `close_run`**, and
`run_stages` is where "no empty mornings" actually lives. A lane is `events.lane`
and is never joined for — `agent_invocations` carries no role, 11 of 1,223 events
have no invocation, and 20 record `system` while their producer is a builder or a
critic. And instants read in the capture timezone, which is also what keeps the
deferred celestial layer unprecluded.

**Two defects only looking at it could find.** The playhead moved by a percentage
transform, which resolves against the element's own width — one pixel — so it sat
at the left edge reporting the correct time, and every automated check passed
because they read the ARIA value. And a lane hue sat within a shade of the
failure color, so a lane with no failures rendered as a lane of failures.

**Still open, and now sharper:** nothing closes a run. `close_run` exists and is
called from nowhere, so every night is permanently in flight. The timeline reads
around it; the night pipeline is where it gets fixed.

---

## Week two and beyond

| Capability | Covers |
|---|---|
| `night-pipeline` | The checkpointed stage machine. "No empty mornings" as executable behavior rather than a schema affordance. |
| `morning-interview` | Briefing from the log delta, then queued questions. The product. Includes the speech visualization below. |
| ~~`retrieval`~~ | **Shipped 2 Sep** — `2026-09-02-add-retrieval`. Detail below. |
| `research` | Tavily search, extract, crawl. Redaction before any query leaves; credit accounting. |
| `artifacts` | Briefs, mockups, builds. Variant grouping and critic ranking; outcome capture. |
| `judge-mode` | The demo instance: cloud profile, synthetic persona, labeled in-UI, "run the night". |

### The capabilities this table was missing

Added 2 Sep. `docs/prompts/00_INDEX.md` names eight gaps "nobody had a plan
for," and six of them had a session prompt but no entry here — which meant the
one document a session reads to decide what to build next could not see them.
A deferred obligation with no home is a dropped one, so they have a home now.

| Capability | Covers | Blocks |
|---|---|---|
| ~~`agents`~~ | **Shipped 2 Sep** — `2026-09-02-add-agents`. Six drafted prompts, pinned by content hash; `deadbeef` is gone. Detail below. | — |
| ~~`configuration`~~ | **Shipped 2 Sep** — `2026-09-02-add-configuration`. Thirteen `SECOND_SHIFT_*` settings, each with the layer it resolved from, and a tree scan that fails when the registry falls behind. Detail below. | — |
| `api-layer` | `api/app.py` is one file five sessions need to add routes to; `api/routes/` is in `ARCHITECTURE.md`'s own tree and does not exist. | nothing, but it de-collides five later sessions |
| `test-harness` | CI gates. Runs any time. | nothing |
| `operations` | The machine: reboot story, backups, a recovery procedure someone has actually executed. Nobody owns it. | nothing, and that is the problem |
| `eval-scoring` | The week-8 run and the curve. `SUBMISSION.md` declares a dependency on it that reads as satisfied and is not. | `submission` |

### `agents` — shipped 2 Sep

Twelve canonical capabilities. Six roles, six drafted prompt files, content-derived
pinning, and the first invocation path that is not a test fixture.

**`prompt_sha` stopped being `deadbeef`.** It is computed from file bytes at
registration and nowhere else. The mutation was run: replacing the hash with a
constant turns four tests red, including the append-only guard — because a
constant hash makes an edit in place undetectable, which is the whole failure
this column exists to prevent.

**The versioning question AGENTS.md posed was already answered by the schema.**
`0001_initial.sql` line 88: `version INTEGER NOT NULL, -- a prompt change is a
new version`. `config/evals/rubric.md` reached the same conclusion independently.
Prompt files are append-only, the filename carries the version, and registration
refuses a file whose content no longer matches what was recorded.

**The six prompts are drafts and say so in their own text.** What a prompt says
is the subject's decision. Replacing one is `v2`, visible in the curve at the
point it happened.

**The real model still shows its work, and that is the finding.** One live call
through the distiller: the completion opens with the literal `Here's a thinking
process:` as prose, *not* inside the `<think>` wrapper observed hours earlier the
same day. The strip trimmed something — a `</think>` did appear later — but what
survived still opens with deliberation. **The wrapper is inconsistent between
calls**, so a strip conditioned on a delimiter handles the observed case and not
the general one. It degrades to verbose rather than empty, which was the design
intent and is the most that can be claimed. 2395 completion tokens for a
one-sentence request.

**Deliberately not done:** per-role `max_tokens`. `Reasoner.complete()` takes no
per-call budget, so this needs the provider interface widened — beyond this
capability, and the token count above makes it matter more than it looked.
Carried into `night-pipeline`, where budgets per stage first bite.

**Ordering, corrected.** `night-pipeline` heads the table above but was not
next: `00_INDEX.md`'s dependency graph puts `configuration` and `agents` ahead of
it. Both shipped on 2 Sep, so **`night-pipeline`'s prerequisites are now
clear** — it has agents to sequence, retrieval to feed them, and a resolved view
that can say which endpoint a stage actually reached.

### `configuration` — shipped 2 Sep

Thirteen canonical capabilities. `python -m secondshift.config show` prints
every `SECOND_SHIFT_*` setting, its resolved value, and the layer it came
from — environment, a named file, or a default.

**The count was the argument.** `docs/prompts/CONFIGURATION.md` was written on
2 Sep saying *ten* variables and listing ten; `retrieval` had added three the
same day. A capability scoped to that number would have shipped three settings
short. So the load-bearing test scans the tree — Python **and** shell, because
`SECOND_SHIFT_RUBRIC_OVERWRITE` is read only by `deploy/spark/deploy.sh` and a
Python-only view has a hole exactly its shape — and fails when the registry
falls behind. Proved by adding a throwaway read to `brain/repo.py` and watching
it go red naming the variable.

**The open decision was the wrong question, and enumeration is what showed it.**
The prompt asked whether an unresolvable required value is a startup failure or
a runtime one. Measuring all thirteen — a script setting each state and recording
what came back, rather than reading the source — says the axis is
**absent versus malformed**:

- **Absent is legitimate for twelve of thirteen** and the existing defaults are
  right. A missing `models.toml` genuinely means "use the defaults." A uniform
  startup-failure rule would have made ten settings worse.
- **Malformed never is.** A mistyped `config/models.toml` was indistinguishable
  from an absent one — both yielded `127.0.0.1:8000` and an empty model name — so
  the probe reported the reasoner **unreachable** while the real cause was a
  syntax error nothing mentioned. An operator would go debug a network that was
  fine. That is the failure this capability exists to end.

**Loud is not fatal, and checking the blast radius changed the design
mid-implementation.** The first draft said a malformed file raises. But
`api/app.py:77` resolves the profile at construction, so raising there takes the
API down — and capture with it — over a file capture never reads. It reports
instead: through the capability finding that depends on it, and through a
non-zero exit a deploy can gate on. `pricing.toml` keeps raising, because it
already did and a silent zero understates a scored measurement; it just names
the file now.

**`SECOND_SHIFT_SYNTHETIC` is the one setting that refuses.** `is_synthetic` is
what keeps seed rows out of a measurement (principle 7), and `SYNTHETIC=ture`
quietly meaning "real data" fails in the direction that cannot be undone.
Failing to start is recoverable; a contaminated eight-week curve is not.

**Still open, and honestly so:** the view has only ever run in this container.
It reports `/root/...` for the database default here and will report the service
account's path on the always-on machine — which is the point, and is also
unverified there. `operations` owns running it on the box.

**Deferred with a handoff rather than dropped:** per-role `max_tokens`, which
this table parked here. The `[agents]` block shape depends on what
`night-pipeline` needs per stage, and a shape guessed now is one that gets
rewritten.

### `retrieval` — shipped 2 Sep

Local embedding behind the existing `Embedder`, exact brute-force cosine over an
in-memory `numpy` array, and policy-filtered assembly. Eleven canonical
capabilities now.

**Both open questions were answered by measurement, not preference**, and the
numbers came from the machine rather than from arithmetic on paper. The index is
rebuilt in memory and never persisted: the real corpus is 6 documents, a rebuild
takes **40ms** steady-state, and the index is **48.0 KiB** — against 48 KB
predicted in the proposal, and 4.70 MiB projected at ADR 0002's own week-8 scale
of ~600 entries. `docs/prompts/RETRIEVAL.md` set the bar at "if rebuilding takes
under a second, the argument for persisting anything is weak." It is
twenty-five times under.

**The embedder is served by vLLM on 8201**, mirroring the reasoner rather than
adding `torch`/`transformers` as a second aarch64-uncertain dependency chain.
The unit shipped `--task embed`, which vLLM 0.27.1 rejects outright; only
running it on the machine found that. `--runner pooling --trust-remote-code` is
correct, and the second of those runs code from the model repository — a real
supply-chain surface, accepted because the repository is NVIDIA's own, and
called out rather than buried.

**Spike B's co-residency question is closed.** It measured the reasoner alone
and could not say whether an embedder fits beside it. Measured with both
serving: reasoner 4.98 GiB RSS, embedder 3.56 GiB, **69 of 121 GiB still
available**.

**Two things this change corrected in accepted documents.**
`docs/ARCHITECTURE.md`'s profile table said the `cloud` embedder was "Token
Factory embeddings" — which constitution principle 2 names as a violation in as
many words. The constitution outranks the table; the embedder is now local on
every profile, the row is fixed, and there is no remote embedder in
`providers/` to select. The same file's "Serverless Endpoints appear to be for
serving models" note is answered by ADR 0009 and no longer open.

**One decision that needed an ADR**: brain topic files carry `local-only`
(ADR 0010). They are distilled from every idea regardless of the policy each was
captured under, so they inherit the most restrictive one. A `cloud-assisted` run
therefore assembles from entries alone — 3 of 6 documents on today's corpus.
That is a real functional limit in the recoverable direction; failing open would
not have been.

**Still open, and inherited by whatever calls this:** nothing calls it yet. The
assembly function exists and is verified end to end against the live model, but
no agent and no night stage consumes it, because neither exists. `night-pipeline`
is where retrieval stops being a capability and starts being memory.

**Two things this capability got wrong about its own compliance, corrected
2 Sep.** Both were self-certified in the proposal and neither was true.

1. **It superseded ADR 0002 and said it did not.** 0002's Decision section reads
   "embeddings are stored as `BLOB`s in SQLite"; the shipped spec forbids
   persisting them. `design.md` asserted "this implements ADR 0002 rather than
   superseding it," and `proposal.md` that 0002 "settled the search mechanism but
   not this." **ADR 0011** records the supersession, what it changes (the storage
   clause only — cosine, no vector database and no native extension all stand),
   and why the archive gate did not catch it: the gate was answered from the
   change's account of the ADR instead of from the ADR.
2. **Its principle-6 row read "nothing in `NOT_BUILDING.md`."** "Vector search
   over the brain" is in that file, under *Deferred, not excluded*, conditioned
   on "only when keyword + recency retrieval demonstrably falls over." **That
   condition was never evaluated** — there is no keyword search and no recency
   ranking in the codebase, so nothing fell over. Not a constitution violation
   (principle 6 enumerates the *Excluded* table) but a deferral gate stepped
   past, and the check that should have surfaced it asserted the opposite.
   Open, and the subject's call: build the keyword + recency baseline and
   measure whether cosine beats it, or record that the comparison will not be
   run. `NOT_BUILDING.md` carries the question.

---

## The drift pass — 2 Sep

The audit's central finding was that the drift that matters is between the
repository and reality, not between documents. This pass closed the
document-to-reality half. Everything below was a document asserting something
that was not true on the machine or in the tree:

| Fixed | Was |
|---|---|
| Schema authority, 4 places incl. `openspec/config.yaml` | Pointed at the wrong file — and `config.yaml` injects it into every proposal, so it propagated |
| Capability counts in `README.md`, `SPEC_ROADMAP.md`, `GRADES.md`, `00_INDEX.md` | Stale numbers; the roadmap header now says to run `openspec list --specs` rather than carrying one |
| `00_INDEX.md`'s "what is true on 2 Sep" table | A frozen snapshot labeled "do not re-derive any of it." Replaced with the commands that derive it, plus a dated table of what cannot be derived |
| Four resolved-but-open nebius markers; the `4a7c2e91b3d0` rubric hash; ADR 0006 pricing | Written out as resolutions; the hash matched no file on the machine |
| `configuration` scope, 10 → 13 variables | Enumerated from source; scoping to 10 would have shipped it three settings short. The roadmap said "wrong by four" — 10 against 13 is wrong by three, and a drift pass that miscounts its own finding is the thing it exists to stop |
| `ARCHITECTURE.md`'s repository tree | Seven entries that do not exist (`NEBIUS_USAGE.md`, `night/`, `morning/`, `api/routes/`, `charts/`, `deploy/tailscale/`, `deploy/nebius/`), and eleven real directories absent — `openspec/` and `config/` among them. Now marks planned ones `(planned)` and says to generate the real tree |
| `WEEK_ONE.md`'s day-3 pass gate | Read as pending; it was missed. Now says which of the four were met, and that the 2 Sep baseline pins a later brain because the day-3 state is unrecoverable |
| Five prompts → six, in `WEEK_ONE.md` and `DATA_MODEL.md` | Six were activated 30 Aug. `DATA_MODEL.md`'s "45 points of noise" derived from nothing in the rubric |
| Spike letters C and D | Collided: the harnesses in `scripts/spikes/` and the plan used them for different spikes. `WEEK_ONE.md` now carries the reconciliation table, and E and F are the two the plan lost |
| `MODELS.md`'s "to verify in week one" | Week one ended with two of three unverified. Each now states its real status; the pricing in `config/pricing.toml` is `eu-north1`'s and the account targets `us-central1` |
| `DATA_MODEL.md` "Vectors are `BLOB`s in SQLite" | Contradicted the shipped spec. See ADR 0011 |
| ADR 0002 and 0004 | Both superseded in part with no forward pointer. Added, bodies untouched — how long a decision stood is part of the record |

**What this pass did not close.** The repository-to-production half. Production
on the always-on machine is 4 days stale, is not a git repository, and the live
database still reads `runs=0, model_calls=0, agent_invocations=0, artifacts=0`.
No document edit changes that, and nothing here should be read as if it did.

---

## Speech visualization for the morning interview

Decided 28 Aug: the interview renders live audio, and it splits into two halves
with very different risk.

**Your speech is buildable now.** `getUserMedia` plus an `AnalyserNode` gives
real-time frequency and amplitude data with no dependency on anything unproven —
Spike A already confirmed `getUserMedia` passes on the phone.

**Its speech no longer waits on TTS.** MagpieTTS was verified on the Spark on
2026-08-28 — five fixed voices, RTF ~0.44, 22.05 kHz. TTS output is audio, and
the same `AnalyserNode` reads it through `createMediaElementSource`. One
component, two sources, and both sources now exist.

**What it must show to be worth building.** A bouncing waveform is decoration and
every demo has one. The version that earns its place visualizes the *turn-taking
machinery*:

- who holds the turn, and whether the system is listening or thinking
- **the moment end-of-utterance fires** — Parakeet Realtime EOU decides this in
  80–160ms, and that decision is the genuinely hard part of push-to-talk
- the gap between speech ending and a response starting, which is the latency a
  person actually feels

That makes it evidence of a working system rather than an animation over one, and
it is the same argument that makes the night scrubber worth building.

**Sequencing.** The input half belongs with `morning-interview`. The output half
is no longer gated on the TTS spike, but must still never block the interview
shipping — the
constitution's text-first principle means every voice interaction has a working
text equivalent, and a visualization of speech that does not exist is not an
exception to that.

## Ordering rule

`capture` before everything, because day-3 dogfooding starts a clock that cannot
be restarted. `nebius-executor` before any cloud reasoning, because the pricing
placeholders make every cloud call fail until it lands. `synthetic-seed` before
`night-timeline`, because a scrubber cannot be built against three events.
