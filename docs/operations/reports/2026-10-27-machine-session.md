# 2026-10-27 — the second machine session

Driven from the laptop over SSH to `<spark>`. Every command below executed on
that machine; nothing ran locally but `git`.

**The headline is not the eval number. It is that `origin/main` cannot be
deployed to that machine.** The live database is at schema 4, applied by a
migration that exists only on an unpushed branch, and `main`'s migrations stop
at 0003 — so `ops doctor` fails there under `main` and passes under the tree
that is actually running. Step 0 was therefore not done, and the reason is in
its own section because everything else in this report had to be arranged
around it. **And the migration that makes `main` undeployable is on no remote
and in no backup** — it exists only on that machine's disk, which is a recovery
finding rather than a tidiness one.

**The second finding is the one to act on.** The judge's refusal rate against
the real checkpoint is **1 of 18**, down from 2 of 5 on 16 Oct — the fix holds.
It is still enough to make the curve unobtainable, because a run is scored as
one indivisible unit of 18 samples and `score` regenerates rather than tops up.
A per-sample failure rate of a few percent is a run-level failure rate near
two-thirds. The week-9 baseline burned on that tonight; the week-1 baseline was
not opened, because the order the subject instructed put the reproducible run
first.

Three days to the deadline. Derived, not typed:
`python3 -c "from datetime import date; print((date(2026,10,30) - date.today()).days)"` → 3.
Current week, derived the same way → **week 9**.

---

## What the prompt assumed, and what was actually there

`ENDGAME.md` step 0 says *"The machine is serving `308e18a`. The judge fix and
payload retention are both newer than that."* Neither half held.

The deployed tree at `~/second-shift` was fingerprinted file by file against
both candidates. Five of six contested files match the unpushed branch
`endgame/finish-openspec` exactly — `telemetry/payloads.py`,
`telemetry/recorder.py`, `config.py`, `ops/backup.py`, `providers/base.py` —
and `evals/judge.py` matches that branch's commit *"fix(evals): read the
judge's final answer whatever came before it"*. The tree also carries three
files that exist on no remote at all: `providers/tokenfactory.py`,
`telemetry/reports.py` and `db/migrations/0004_external_keys.sql`.

So production is running a line of work that was never pushed. The 16 Oct
report's *"production, redeployed at `308e18a`"* was true when written and is
not true now; something deployed from that branch on 17 Oct, and the database
carries the consequence.

**The session clone `~/second-shift-src` was behind the thing it had deployed** —
at the branch's `feat(operations)` commit, two commits older than the judge that
production runs. Its virtual environment was intact. Both venvs live at
`apps/api/.venv`, not at the tree root; a first probe looked at the wrong depth
and wrongly reported them missing.

---

## Step 0 — the deploy. **Not done, deliberately.**

`0004_external_keys.sql` adds an `external_key` column to `agent_invocations`
and to `model_calls`, plus two partial unique indexes. All four objects are
present in the live database and `schema_version` records the migration as
applied on 17 Oct. The schema is genuinely at 4.

`doctor`'s schema check is `applied != expected` — strict in both directions —
and `expected` is the highest migration *on disk*. So:

| Tree | Result |
|---|---|
| `~/second-shift`, the deployed branch code | **8 of 8 passed**, `ok schema at 4`, exit 0 |
| `~/second-shift-src` at `origin/main` | **1 of 8 failed**, `FAIL schema at 4, migrations on disk go to 3`, exit 1 |

Deploying `main` would also have removed capability from production rather than
adding it. `config.resolve_all` returns **17 settings under the deployed tree
and 16 under `main`**; the difference is `NEBIUS_API_KEY`, because the Token
Factory provider is part of the unpushed branch. `telemetry/reports.py` would
have gone the same way.

`deploy.sh` does `rm -rf` on the target tree. Running it would have destroyed
the deployed copy of three files that are on no remote, and left `doctor` red. **It was not run.** The
rubric guard would not have caught any of this: the target's rubric already
hashes `b4decd6fe774`, the hash the week-1 baseline pins.

**Recommendation.** Land `0004_external_keys.sql` and the Token Factory provider
on `main` before any deploy to that machine. Until then `main` is not a
deployable artifact for `<spark>`, and the step-0 instruction cannot be followed
as written. This is a question for the subject and not a decision this session
made.

**What was done instead.** Step 0's purpose is *"scoring before deploying scores
with the instrument that failed."* That purpose was served without a deploy: the
session clone was checked out at `origin/main` — detached, so no branch ref
moved — its dependencies reinstalled with `pip` and `constraints.txt`, never
`uv`, and every eval below was run from it. Production was left untouched.

---

## Where that unpushed work actually lives, and what a disk failure would take

Step 0's recommendation is a tidiness item until you ask where those three files
are. Then it is the most serious finding in this report.

**Verified, not inferred.** `0004_external_keys.sql`,
`providers/tokenfactory.py` and `telemetry/reports.py` exist at commit
`fd58853`, reachable as `bundle/finish` in two repositories on that machine and
as its detached `HEAD` in one of them, plus three `*.bundle` files in `$HOME`.
So the work **is** in git, several times over.

Every one of those copies is on the same disk.

| Where | Holds it |
|---|---|
| `origin` — `github.com/mgraves-centrix/second-shift` | **no** — checked every remote ref |
| The laptop clone | **no** — checked every local and remote branch for the file |
| `<spark>`, two repositories + three bundles | yes |
| `~/second-shift`, the deployed tree | yes, as plain files — **it is not a git checkout at all** |
| **Every backup** | **no** |

That last row is the finding. The archive holds `second-shift.db`, `artifacts/`,
`payloads/` and `manifest.json`, and excludes the code deliberately, with the
reason written into every manifest:

> `excluded    deployed tree — reproducible from git; deploy.sh destroys and recreates it`

**For this commit that sentence is false.** The only git that has it is on the
disk the backup exists to survive. The exclusion is correct in principle and
wrong in fact, and nothing in the system can tell the difference — which is
exactly the failure mode `RECOVERY.md` was written against, one level up from
where it was looking.

**What that costs on the day the disk fails.** The live database is at **schema
4**, applied by that migration. Restore the newest backup onto a new machine and
you get a schema-4 database with no migration on disk that reaches 4. `migrate`
skips every version at or below the current one, so it raises nothing;
`doctor` fails with `schema at 4, migrations on disk go to 3` — the same line
`main` produces today. The recovery looks like it worked and the system is on a
schema nobody can reproduce. `RECOVERY.md` says the deployed tree is the one
thing whose loss costs *"nothing"*. Today it costs the schema.

**The fix is one push**, and it is the subject's to make: this repository is
public, and that branch carries a Token Factory provider that has never been
through the no-environment gate on its way to a public remote.

---

## Step 1 — `ops doctor`. Evidence.

8 of 8 under the deployed tree, reproduced above. The checks worth quoting:

- `ok data ownership  default under ~` — the account this session logged in as
  is the account the units run as, so the SSH caveat in the prompt does not
  apply. Confirmed rather than assumed.
- `ok local reasoner  <addr>:8200 serving nemotron-3.5-lightning`
- `ok backups  16 backups, newest 0.8 days old` — **four on 16 Oct, sixteen
  now.**
- `ok backup location  <nas>/scratch/second-shift-backups is on another device`

`SECOND_SHIFT_PAYLOADS` resolves on both trees, to `~/second-shift-data/payloads`.
**That directory did not exist when this session started**, which is consistent
with the table having never held a row.

### The nightly backup chain is real, and this is the first evidence of it

The 16 Oct session installed the backup unit and added `Wants=` to the night
unit, but could not show the chain firing on a schedule. It fires:

- `second-shift-night.timer` last fired **Tue 2026-10-27 02:00:09**, next
  Wed 02:00.
- `second-shift-backup.service` reports `Result=success`, `ExecMainStatus=0`.
- Backups went 4 → 16.

It fires even though **no night has had work to do since 18 Sep.** The `runs`
table's newest row is `2026-09-18`, three `complete` and three `degraded` before
it. The timer runs, the night finds nothing queued, and the backup is pulled in
anyway — which is the behavior the `Wants=` was argued for.

---

## Step 2 — the smoke test, on a throwaway copy

**`ENDGAME.md`'s instruction for this step is unsafe and was not followed
literally.** It says to `cp` the database aside. The live database is 286 KB and
dated 18 Sep; beside it is a **4 MB write-ahead log** dated 17 Oct. A file copy
would have produced a September database that restores cleanly — exactly the
failure `RECOVERY.md` devotes a paragraph to, in the one step whose whole job is
to produce a trustworthy number. `VACUUM INTO` was used instead, against a
read-only handle on the live file.

The snapshot carried schema 4, 46 model calls, 2 eval runs and 7 entries,
matching the live database.

### On the throwaway copy, the judge refused **0 of 12**

This is the number the last session stopped over, and the 26 Oct fix moved it.
It is not this report's answer — the run it belongs to died on infrastructure
at sample 12, and the rate against the **real** checkpoint is further down, at
1 of 18.

| | 16 Oct | 27 Oct |
|---|---|---|
| Smoke test, throwaway copy | 1 refused of 18 | **0 refused of 12** |
| Real run, before it was stopped | 2 refused of 5 | not reached |

Not one `UnreadableJudgement`. No sample failed at character 29, and no sample
failed at all on the judge's parse. The template is gone from `_ASK` and `score`
tries every top-level object last to first; on every sample this run reached,
both held.

**The run still did not complete, and the cause was not the judge.** After 12
samples the vLLM engine died:

```
torch.AcceleratorError: CUDA error: an illegal memory access was encountered
  vllm/v1/attention/backends/flashinfer.py:1234
  → vllm/v1/attention/backend.py:515   self._seq_lens_cpu = self.seq_lens.to("cpu")
```

The engine was serving under `speculative_config=SpeculativeConfig(method='mtp',
num_spec_tokens=3)`, and the dumped scheduler output carries
`scheduled_spec_decode_tokens: [-1, -1, -1]` for all three in-flight requests.
Negative token slots reaching an attention kernel are a plausible illegal
address, and the crash is raised from the speculative-decode path. vLLM
v0.27.1, NVFP4 weights, `kv_cache_dtype=fp8`.

The failure was recorded as `network:reasoner:local-vllm:...`, a 500 from the
reasoner, **not** as a scoring refusal. Four prompts completed all three samples;
`readme-in-my-voice` and `shorter-briefing` got none.

#### Why this matters more than the refusal rate it replaces

Every protection in `ENDGAME.md` is built around the judge refusing a sample.
**A mid-run engine crash burns a run by exactly the same mechanism:**
`eval_results` is `UNIQUE(eval_run_id, eval_prompt_id, sample_index)` and
`EvalRunner.score` regenerates every sample rather than topping up, so a run
that dies at sample 13 can never be completed. The instrument's *parse* is
fixed; its *stability* is now the binding risk to the one artifact that cannot
be remade, and it took twelve samples with it rather than one.

The reasoner's own unit recovered it — `NRestarts=1`, back to serving in
**6 minutes 32 seconds** from a warm cache. That is the unit work of 16 Oct
doing what it was installed for, and it is also a second independent
measurement contradicting `SUPERVISING_THE_REASONER.md`'s "roughly three
minutes".

#### `model_call_payloads` holds rows, for the first time

**24 rows** in the throwaway at the point the run died, under
`~/smoke-2026-10-27/payloads/`. The table had never held a row in its life
before today. Count and path only; the contents stay on that machine, which is
the whole point of the table.

**`eval_results.output_path` was populated on 12 of 12 scored samples.** It was
NULL for all 17 on 16 Oct, which is why nobody could read what had been scored.
Both of the things this session was told to check rather than assume are true.

#### What was changed to get past it

Speculative decoding was removed from the reasoner's serving configuration by a
systemd drop-in at
`~/.config/systemd/user/second-shift-reasoner.service.d/no-spec-decode.conf`.
It clears `ExecStart` and restates it without `--speculative-config`; every
other flag is byte-identical. The committed unit file is untouched, so a deploy
does not conflict with it — **and will not remove it either, which is the risk
this paragraph exists to record.**

**This change is invisible in the data, and that is a real problem.**
`eval_runs.judge_model_version` pins the instruction (`ask_sha()`) and the
served model name. It does not pin the serving configuration, so two runs scored
either side of this drop-in are indistinguishable in the database — the same
asymmetry the unpinned `_ASK` had, in a different place. The drop-in carries its
own removal instructions in a comment for that reason.

This was put to the subject before it was done, with that cost named, and the
answer was to make the change and re-measure. **It is not a loosened refusal:**
the judge's parse, the curve's ten refusals and the airlock's policy constant
are all untouched.

#### Then it was re-measured, not assumed

A second smoke test was started on a **fresh** snapshot with spec decode off,
chained to steps 3 and 4 behind the same condition: 18 of 18 scored and 0
refused, or stop and leave the week-1 baseline alone.

It finished at 21:54:31, 63 minutes after it started: **18 of 18 scored, 0
refused, 36 payload rows, `output_path` 18/18**, overall mean 17.11. The
reasoner came back in about 150 s against 6m32s with speculative decoding on,
because there is no draft model to load and compile. No CUDA fault.

So the condition was met and the chain went on to steps 3 and 4 without me. What
it found there is more important than the refusal rate.

### Step 3 — the backup, and the one before the one that mattered

`2026-10-28T01-54-31Z`: 243 rows across 17 tables, schema 4, 39 artifact files,
and **`payloads` 0 files, 0 bytes**. Hold that zero; it is load-bearing two
sections down.

### Step 4 — the week-9 baseline. **16 of 18. The run is burned.**

Recorded as `01M603EMRKP4726R93WQGMNA91` against brain `e68cecf961de` and rubric
`b4decd6fe774` — the same inputs as the smoke run, the same judge, the same
served model, the same spec-decode-off configuration. Scored on the **real**
database, finishing 22:46:43 with `complete=False` and
`readme-in-my-voice` at `n=1` of 3.

**Two events, recorded as three rows.** The distinction is the finding, so each
one is named rather than totalled:

| Time | Signature | What it actually was |
|---|---|---|
| 22:32:23 | `eval:readme-in-my-voice:UnreadableJudgement` | **The judge refused.** It wrote no JSON object at all — not a truncated one. |
| 22:38:01 | `bad_output:invocation:f6db691846fdca57` | The **architect** stopped at `length` after 16,000 completion tokens. |
| 22:38:01 | `eval:readme-in-my-voice:TurnDidNotFinish` | The same event, three milliseconds later, recorded a second time by the eval runner. |

**So the judge's refusal rate against the real checkpoint is 1 of 18, and the
other failure is not the judge's at all** — it is the candidate generator
running out of budget. The two messages quoted above are the code's own strings
from `judge.py` and `invoke.py`; the judge's actual text is in
`model_call_payloads` and is not reproduced here.

My own guard reported "3 failed" because it counted rows in `failures`. That is
the right thing for a stop-or-go gate and the wrong number to report, and it is
mine, not the system's: the system recorded one event at two levels on purpose,
because the invocation closes as a failure and the runner records its own.

### The guard fired. The week-1 baseline was not scored.

```
=== STOPPING: the week 9 run did not complete cleanly ===
The week-1 baseline 01M1FYFECEXC5ZJEWHNP7WZMXB is NOT being scored.
```

This is the instruction the subject gave — week 9 first, week 1 last — doing
exactly the work it was given to do. The reproducible run absorbed the damage
and the irreplaceable one was never opened. `eval_runs` has no uniqueness on
`week_of` (`0001_initial.sql`), and the brain has not moved since 18 Sep, so a
fresh week-9 baseline can be recorded and scored. Nothing about week 1 can be
retaken.

### What this says about the curve, which is worse than the refusal rate

`score` regenerates rather than tops up and `eval_results` is
`UNIQUE(eval_run_id, eval_prompt_id, sample_index)`, so **`complete` is
all-or-nothing across all 18 samples**. One bad sample anywhere burns the run.
That turns a small per-sample failure rate into a large run-level one:

| | Per sample | Chance of a clean 18 |
|---|---|---|
| Judge refusals alone, 1 in 36 real samples today | 2.8% | ~60% |
| Both run-burning events, 2 in 36 | 5.6% | **~36%** |

Two events is far too few to pin a rate, and saying so is part of the result:
the 95% interval on 2 of 36 runs from 1.5% to 18.1% per sample, which puts a
clean 18 anywhere between **3% and 76%**. The width is the honest finding. The
point estimate is not.

**So the curve is not blocked by the judge. It is blocked by the gate around
it.** The 26 Oct fix did what it was supposed to — the judge refused once in 36
rather than twice in 5 — and a rate that low is still enough to make a clean run
roughly a coin flip, because the run is scored as one indivisible unit. Scoring
the week-1 baseline tonight would have meant accepting something near a
two-in-three chance of destroying the only artifact in this system that cannot
be remade, to obtain a number.

**The fix is a top-up path in `score`, not a better judge.** `judge.py` already
reasons at length about the asymmetry between a draft judgement and a destroyed
baseline, and resolves it by preferring the draft. The same asymmetry one level
up has no such treatment: a run that scored 16 of 18 cannot be asked for the
other two. Everything else here — ordering the runs, pinning the rubric,
refusing a truncated judgement — is protection against a failure the design
makes unrecoverable rather than merely annoying.

The architect's truncation is a second, smaller finding of the same kind.
`reasoner_max_tokens` was raised from 4096 to 16000 after the first real night
lost three of six turns inside their deliberation; at 16000 it happened once in
18. Raising it a third time is the obvious move and probably the wrong one — the
same prompt, `readme-in-my-voice`, also carried the judge refusal and had the
widest spread in the smoke run (sd 4.93). Something about that prompt makes this
model deliberate without converging, and a larger budget buys a longer version
of the same behavior.

### The first backup in this project's history that carries payloads

The chain exited 1 at the guard, before its own closing backups, so this one was
taken by hand afterward:

| | `2026-10-28T01-54-31Z`, before the runs | `2026-10-28T02-48-02Z`, after |
|---|---|---|
| Database | 243 rows, 17 tables, schema 4 | 352 rows, 17 tables, schema 4 |
| Artifacts | 39 files, 164,820 bytes | 39 files, 164,820 bytes |
| **Payloads** | **0 files, 0 bytes** | **70 files, 1,024,053 bytes** |
| `verify` | intact, 40 members | intact, **110 members**, 0.17 s |

`RECOVERY.md` has promised a `payloads/` tree since the first backup and said of
the 16 Oct restore that "payloads were not part of that restore, because there
were none to carry. The next one is the first that exercises them." Those two
archives, an hour apart on the same machine, are that sentence being closed:
the mechanism was already correct and had never once been given anything to
copy. `verify` reads the new tree against its recorded digests in 0.17 s.

A restore of the payload-carrying archive was **not** run, and that is now the
gap `RECOVERY.md`'s restore section has instead of the one it had this morning.

---

## Step 5 — one real night. **Not attempted.**

`entries` holds 7 rows: **6 `answered`, 1 `archived`. Nothing is queued**, so
there is no work for a night to do. Identical to 16 Oct. Fabricating an entry
would have put a made-up idea in the real database marked `is_synthetic = 0`;
not done.

This needs an idea captured from the phone, which is also `RECOVERY.md`'s
acceptance test. `2026-09-17-the-night-revises-what-it-believes` stays at 6/7.

---

## Step 6 — the reboot. **Not possible from here.**

`sudo -n true` reports `a password is required`. A session over SSH cannot
reboot that machine. Uptime is **51 days**, up from 5 weeks 5 days on 16 Oct.

What this session could do was establish whether the reboot is *prepared*, which
nobody had checked:

| | |
|---|---|
| `Linger` | `yes` — user units start at boot without a login |
| `second-shift-api.service` | enabled, active |
| `second-shift-reasoner.service` | enabled, active |
| `second-shift-night.timer` | enabled, active |
| `second-shift-brain-sync.timer` | enabled, active |
| `second-shift-backup.service` | static, inactive — correct; the night pulls it in |

**A first reading of this looked like a finding and was wrong.** The embedder
runs as a bare Docker container with no unit installed anywhere, and
`second-shift-embedder.service` ships in `deploy/spark/` without being
installed — which looked like the embedder would not survive a reboot. It will:
its restart policy is `unless-stopped`, so Docker restores it. The reasoner's
policy is `no`, and that is also correct, because its systemd unit owns the
container's lifecycle. The two mechanisms differ and both hold.

So the reboot looks safe to attempt. It still needs somebody at the machine, and
it remains the only evidence that the 16 Oct unit work did what it was for.

---

## The gates on that machine — run for the first time

`scripts/gate.py` stops at the first failure and has no skip mechanism, and two
of its eleven gates cannot run there at all. The runnable ones were run
individually instead, which is what *"run what does run and say which gates were
skipped"* asks for.

**Everything in this table is from a run made from the repository root with
`env -C`.** An earlier pass was made from `$HOME` and is not reported here,
because it measured my working directory rather than the code; what it got wrong
is below, and why, because the next session will be tempted the same way.

| Gate | Result on `<spark>` |
|---|---|
| `airlock` | **pass** — 22 tests, 0.30s |
| `no environment details` | **pass** — *clean: no environment details in tracked or new files* |
| `American English` | **pass** — *clean: American English throughout* |
| `drift` | **pass** — 247 tracked documents, both directions |
| `api` | **2 failures of 930**, 928 passed, **711.88s** |
| `judge package` | **pass** against the judge image's baked database |
| `mutations` | not completed |
| `specs` | **cannot run**: no `openspec` CLI |
| `browser` | **cannot run**: no Chrome |
| `web unit`, `web types`, `web build` | not attempted: no `node_modules` in the session clone |

**What the first pass got wrong, and it was mine rather than the project's.** It
ran each gate with absolute paths from `$HOME`, per this project's own
absolute-paths-everywhere rule. Several gates resolve paths **relative to the
repository root**:

- the api suite reported **8 failures**, of which **7 were the working
  directory** — `FileNotFoundError: config/evals/threshold.md`, the CLI's
  relative default for `--threshold`.
- `check-no-environment.sh` and `check-american-english.sh` returned 0 in 0
  seconds, which for a repository scan is not a pass, it is a scan of nothing.

`scripts/gate.py` must run from the repository root, and `env -C <root>` gets
that without a working directory that outlives the command.

**The api suite takes 11m51s on that machine and spends almost none of it
computing** — about 20 seconds of CPU across the unit. It is dominated by stub
HTTP servers and real timeouts. Worth knowing before somebody reads a quiet
eleven minutes as a hang: I did exactly that, looked at a main thread blocked in
`anon_pipe_read` and three write-end pipe descriptors, and called it a deadlock.
It was ordinary capture plumbing and the suite finished on its own.

### Both failures are one defect, and it is not the machine's fault

```
apps/api/tests/test_operations.py::TestDoctor
  ::test_an_unreachable_reasoner_fails_where_one_is_expected
apps/api/tests/test_evals.py::TestTheScoreCommand::test_no_local_reasoner_refuses
```

The first sets `env[ENV_LOCAL_PORT] = "9"` and asserts the local-reasoner check
fails. It got:

```
Check(name='local reasoner', ok=True, detail='127.0.0.1:8200 serving nemotron-3.5-lightning')
```

**Port 9 was discarded. The check probed 8200.** `run_checks(env=...)` passes
its dictionary to `config.resolve_all(environment)`, which honors it for the
profile, the database, the brain and the location — and builds the reasoner and
embedder rows from `local_reasoner_settings()`, a function that takes no
argument and reads `os.environ` and `config/models.toml` directly
(`config.py:673`, `config.py:684`, `local_endpoint()` at `config.py:201`).

So **six of `resolve_all`'s settings ignore the environment it is given**: the
reasoner's host, port and model, and the embedder's. A caller that passes an
environment is silently handed the machine's real values for those six. Two
functions in the same module disagree about whether `SECOND_SHIFT_LOCAL_PORT`
works: `local_endpoint()` honors it from the process environment,
`resolve_all`'s row for it does not honor an injected one.

This is the **same shape** as the capability-probe finding below — configuration
that reads as injectable and is in fact taken from process state — and it is why
these two tests pass on every machine without a reasoner on 8200 and can never
pass on the one machine that has one. They are not testing what they read as
testing: the address they choose is thrown away.

The fix is to thread `environment` through `local_reasoner_settings()` and
`local_embedder_settings()`. Until then **the api suite cannot go green on the
always-on machine**, and the roadmap row should say that rather than "the gate
has never run there".

### The capability probe is resolved once, at process start

Found while standing up a second API against seeded data, and confirmed in both
directions rather than inferred:

- An API started **while the reasoner was down** reported
  `profile: cloud, degraded: true, local-only unavailable`, and **kept
  reporting it after the reasoner recovered.** Restarting that process cleared
  it immediately.
- The production API, started long before the 20:31 reasoner restart, reported
  `profile: workstation, local-only available` throughout — including while the
  reasoner was actually down.

`resolve_profile()` run directly, under a minimal environment, returns
`workstation` with no degradation. So the staleness is the process holding its
startup resolution, not configuration: `_MODELS_CONFIG` is
`Path(__file__).resolve().parents[3]`, so the working directory never enters
into it.

**The consequence is for the reboot.** `second-shift-api.service` carries only
`After=network-online.target` — no ordering on the reasoner and no readiness
wait — and the reasoner needs **6m32s** to serve. On a reboot the API wins that
race by minutes, caches "no local reasoner", and reports `local-only`
unavailable until somebody restarts it.

Principle 2 requires that where a profile cannot honor `local-only` the UI must
say so rather than silently downgrade. It does say so. The defect is that it
goes on saying so once it is false, and the night unit already carries a comment
about this exact class of race.

### The demo night's `outcome: null` is the seed, not the container

The 16 Oct session recorded that the judge image's demo night returns
`outcome: null`, and attached it to the image. It is not the image. Three nights
seeded into a throwaway database with `packages/seed` return
`outcome: null`, `furthest_stage: null`, `ended_at_ms: null` from `/runs` on an
ordinary API.

**`close_run` is never called anywhere in `packages/seed`.** The seed calls
`insert_run` at `night.py:608` and `insert_run_stage` at `night.py:640`, and it
closes every *invocation* with an outcome (`night.py:1012`); a real night closes
the run itself at `night/run.py:486`. The seed's night therefore never ends. Its
1,314 events, 182 invocations and 362 model calls are all there, in a run that
reads as still in flight.

`close_run`'s own docstring predicted the consequence before this seed existed:

> Without this nothing ever set `ended_at_ms`, so every run looked like it was
> still in flight — including finished ones, which makes "how long did last
> night take" unanswerable from the data.

So the fix belongs in `packages/seed`, where it also fixes the judge image,
rather than in `deploy/judge/`. It is one call at the end of `generate_night`
with an outcome and a furthest stage the seed already knows.

This was found with the sample data this session was asked to load, which is
what that exercise was for — and then confirmed in the built image, below.

**Cannot run on that machine:** `specs` (no `openspec` CLI) and `browser` (no
Chrome). Both were already recorded as blocked on 16 Oct and both remain so.
Installing a browser on the always-on machine is a decision about that machine,
not a step in this session.

**Not attempted:** `web unit`, `web types`, `web build` — the session clone has
no `node_modules`, and `npm ci` there during a scoring run is contention for no
new information. `node` and `npm` are both present, so these are installable.

---

## `eval_runs.code_sha` is never written

`EvalRunner.record_baseline` takes `code_sha: str = ""` and **no caller ever
passes it.** Both recorded runs have it empty, and so does the one this session
recorded.

This is the same shape as the two defects this project has already found and
closed — `close_run has no caller`, and `insert_model_call_payload has no
caller`. A parameter with a default and no caller is indistinguishable from a
field that was never meant to be filled.

It costs something specific here. A run records the brain it read, the rubric it
pinned and the judge that graded it, but **not the code that produced it** — so
the fact that this session scored from a clone at `origin/main` while production
runs a different tree is invisible in the data. Nothing in the database
disagrees with anything; there is simply no field that would have noticed.

Not fixed in this session: it is a schema-adjacent change to the table the
submission's centerpiece is read from, made on a day when the centerpiece had
not yet been measured.

---

## What `docs/SUBMISSION.md` still claims that is now wrong

Independent of the eval result, one row is stale against the **16 Oct** session,
not against this one:

> `| **The judge container built and stood up** | **Not run** |`

It was built, stood up and read on 16 Oct. That row can move regardless of
anything here, with the `arm64` caveat and the `outcome: null` demo night
attached.

### And four rows this session's evidence changes

The whole of `eval_runs` on the real database, after tonight:

| Run | `week_of` | Brain | `judge_model` | Scored |
|---|---|---|---|---|
| `01M1FYFECEXC5ZJEWHNP7WZMXB` | 2026-08-31 — week 1 | `ad17b3bcddb6` | `awaiting-scoring` | **0 of 18** |
| `01M53FX6MV5D9ZWF4Z6117YVSE` | 2026-10-15 — week 8 | `e68cecf961de` | `awaiting-scoring` | **3 of 18** |
| `01M603EMRKP4726R93WQGMNA91` | 2026-10-26 — week 9 | `e68cecf961de` | `nemotron-3.5-lightning` | **16 of 18** |

**Not one of the three is complete, all three are still open, and two of them
can never be finished.** That is the submission-relevant fact, and it is not
tonight's bad luck: the week-8 run was burned on 16 Oct at 3 of 18, by the same
mechanism, and its `judge_model` is still `awaiting-scoring` because that
session's process stopped inside the sampling loop before the closing `UPDATE`
ran. Two attempts on the real database, two burned runs. Week 1 has never been
opened, which is the one thing that went right both times.

The brain did move: `ad17b3bc` at week 1 against `e68cecf9` now. The curve has
two genuinely distinct brain states to compare. It has no two complete runs.

So the rows:

**Line 197 — `| The week-8 eval score | Not run. |`** should not become "Run",
and it should not stay "Not run" either. Both are less informative than the
truth: *scored 27 Oct against week 9's checkpoint and came back 16 of 18 with
`complete = False`; the judge refused 1 of 18, the candidate generator truncated
1 of 18, and a run is all-or-nothing, so neither partial result can be
completed.* A row with a number and a reason is a better submission than a row
with a status.

**Line 208 — what the eval score waits on.** It reads "**A session on the
machine.** ADR 0015 made the judge local, so this needs no credential at all."
Both sentences are true and the conclusion no longer follows. Two sessions on
the machine have now run it. What it waits on is **a top-up path in `score`** —
code, not access — and no session on that machine can supply it.

**Line 198 — `| The judge container built and stood up | Not run |`** is stale
against 16 Oct, as the paragraph above this one says, and that is unchanged by
tonight except that `main` now builds it too.

**Line 209 — what the judge container waits on.** It reads "**A container
runtime.** Every step inside the image has been run outside it; the layering has
not." The machine has Docker 29.2.1 and the layering has now been run twice.
What it waits on is a **cross-build for the deployment target's architecture**,
which is a different and smaller thing.

**Line 233 — "As of 16 Oct that comparison has not been run"** is accurate as a
dated statement and should stay one. What it says next is now wrong: "the only
eval run in the system still reads `judge_model = 'awaiting-scoring'`" — there
are three runs, two of them read that, and the table above is what replaces the
sentence.

None of these are edits this session made. `docs/SUBMISSION.md` is a document
that claims things to a reader who cannot check them, and a machine session that
changes what is true owes it a list rather than a rewrite.

---

## The credential question

**Recommendation: leave it on the machine. Nothing needs to move — and this
session found a second reason, which is that the credential is no longer the
binding constraint.**

The 16 Oct recommendation was that driving the machine over SSH puts every
command where `~/.config/second-shift/secrets.env` already is, so the Nebius
rows are reachable without copying anything. This session was shaped the same
way and confirms it again: nothing in it needed a key in a second place.

What is new is that **the Nebius work is not only blocked on a key.**
`providers/tokenfactory.py` — the cloud reasoner, priced by the ids it serves —
exists on the unpushed `endgame/finish-openspec` branch and on the deployed tree,
and nowhere else. `main` does not have it, which is why `main` resolves 16
settings and the deployed tree resolves 17. So:

- **Leave the key where it is.** Costs nothing but the constraint that the work
  happens on that machine or over SSH to it. The RS256 Cloud IAM private key
  never exists in a second place.
- **Copy it.** Buys work from a cloud session. Costs a private key in a second
  location, permanently, to lift a constraint two sessions have now shown is not
  binding.

The decision that actually gates the Nebius rows is the first one in this
report: whether that branch lands on `main`. A key in a cloud session with no
Token Factory provider on `main` buys nothing.

---

## The sample data, and what it was allowed to touch

This session was asked to load sample data to verify functionality. **It was not
loaded into the real database or the canonical brain**, and the reasons are
Principle 7 and Principle 5: a row written by hand lands `is_synthetic = 0`, and
`synthetic_flag()` is written to raise rather than guess precisely so that seed
rows can never become indistinguishable from real ones. A scoring run was also
in flight against that database at the time.

What was done instead used the mechanism the project already has:

- Three deterministic nights from `packages/seed` into a throwaway database —
  **26 entries, about 611 invocations, 1,232 model calls and 4,100 events, every
  row `is_synthetic = 1`.**
- The brain **cloned** to a throwaway path, never written to. Principle 1: a
  copy is a clone, never the original.
- An API served against both on a port production does not use, under
  `systemd-run`, with `SECOND_SHIFT_SYNTHETIC=true`.

`/health`, `/capabilities` and `/runs` all answer correctly against seeded data.
It found the two findings above — the cached capability probe and the seed's
unclosed runs — neither of which a real-data exercise would have been allowed to
look for.

One note for whoever runs the seed next: `secondshift_seed`'s `DEFAULT_DB` is
the **real** database path. It takes `--db`, and it should always be given one.

---

## The judge instance — rebuilt from `main`, and one near-miss worth keeping

**This is the second build, not the first.** The 16 Oct session built it, stood
it up, and recorded both of its findings — `arm64`, and the demo night with no
outcome. What is new here is narrow, and the section is short because of it.

Built from the session clone at `origin/main` — the tree the deployed branch is
*not* — from the repository root, with no `cd`:

```
docker build -f <repo>/deploy/judge/Dockerfile -t second-shift-judge:2026-10-27 <repo>
```

96 seconds, exit 0, `arm64`, 268,940,057 bytes. The web export, the pinned
Python install, the seeded night and `check-judge-package.py` all ran inside
the build. Stood up: `/health` `{"status":"ok"}`, `/` 200 at 7,355 bytes,
`/capabilities` → `profile: cloud` with `local-only` unavailable for the reason
the Dockerfile argued for, and the ship gate re-run by hand inside the running
container: `clean: ... carries nothing a judge deployment must not hold`.

So **`main` builds a correct judge image** — which is the only new fact in that
paragraph, and it is worth having, because `main` is the branch that cannot be
deployed to the always-on machine and this is the one artifact it still
produces.

### A `200` from the wrong process nearly became a verification

The first run failed to bind a port already held by the verify instance from the
sample-data work. `docker run` printed `address already in use` and exited
non-zero — and the three `curl` calls after it answered `200` anyway, **from
that other instance**, reporting `profile: workstation` and `local-only`
**available**: the opposite of what this image exists to show. I was one paste
away from recording it as the judge instance working.

What caught it was reading the `docker` error rather than the HTTP codes. The
lesson is narrow and worth keeping: **`/health` identifies a listener, not an
image.** Every probe above reports something only the intended build could say,
which is why the profile is quoted and the status code is not.

### What it carries, counted

| Table | Rows | `is_synthetic = 0` |
|---|---|---|
| `model_call_payloads` | **0** | — |
| `entries` | 5 | **0** |
| `runs` | 1 | **0** |
| `agent_invocations` | 182 | **0** |
| `model_calls` | 362 | **0** |
| `events` | 1,232 | **0** |

16 Oct confirmed the image holds nothing real; this adds the row counts and the
explicit zero on `model_call_payloads`, which matters more now than it did then,
because that table **stopped being empty on the real machine today**. The build
takes none of it: the database is written from a seed inside the image and the
`COPY` lines name what they take.

### `docs/prompts/JUDGE_MODE.md` no longer describes this seed

It states, for `--seed 42`: "1,223 events over 7.32 hours across 7 lanes, 182
invocations at depth 3, 362 model calls with costs, 6 failures." The invocations
and the model calls match exactly. The events are **1,232 across 8 lanes** and
the failures are **10**.

That matters more than a stale figure usually would, because the sentence those
figures support is *"deterministic by seed, so a screenshot is reproducible"* —
the figures were the check on that claim, and they no longer check it. The seed
is still deterministic; nobody can tell from the document which night it now
produces.

**A discrepancy that is not a defect**, recorded because I had to chase it:
`/runs` reports `event_count` 1,227 while `events` holds 1,232. The five are
lane `capture`, kind `note`, one per seeded entry, with `run_id IS NULL` — ideas
captured outside any night, which the run's count correctly excludes. Three
numbers — 1,223, 1,227, 1,232 — appear within a screen of each other and only
one of them is wrong.

### Both 16 Oct findings still stand, and one of them now has a cause

The **`arm64`** caveat is unchanged, and the cross-build is still owed before
this is deployed anywhere. One correction to how it was written down: the 16 Oct
report says "ADR 0009 puts this on a no-GPU **x86** Compute VM". **The ADR does
not say that.** It prices a `2vcpu-8gb` preset and names no architecture
anywhere. The conclusion is very probably right — a vCPU preset normally means
`x86_64` — but it is an inference, the ADR is the document that should have
settled it, and nobody can check it from the repository. Verifying it needs the
Nebius console, which needs the credentials this session is not allowed to read.

The **demo night with no outcome** is unchanged in the image and now traced to
its line: `close_run` is never called in `packages/seed`. That is the finding
above, and the fix is one call.

No deployment was attempted — the cross-build is unresolved, and publishing the
demo is an outward-facing action nobody authorized tonight.

---

## Where this report's method failed

Recorded because a report that only lists what worked cannot be used to judge
its own numbers.

- **`ssh -n` nullifies a heredoc.** `-n` redirects stdin from `/dev/null`, so
  five scripts written by piping a heredoc through `ssh -n` landed as 0-byte
  files and exited 0 silently. One of them was the guard that was supposed to
  stop step 4 after an unclean smoke test. **The real database was untouched,
  but that was not the guard's doing** — it was confirmed by querying the
  database directly. The guard is now in place, syntax-checked, and every
  long-running job is started with `systemd-run --user` rather than
  `setsid nohup`, which does not survive the session that launches it either.
- **Three readings were wrong before they were right.** The virtual
  environments looked missing to a `find -maxdepth 3` and are at depth 4; a
  degraded capability probe looked like a working-directory problem and was a
  cached resolution; the embedder looked like it would not survive a reboot and
  will, by `unless-stopped`. Each is corrected in place above rather than
  quietly dropped.
- **`doctor`'s exit code was briefly misread** as 0-on-failure, because `$?`
  after a pipe is the last command in the pipe. It exits 1 correctly.
- **A `200` from the wrong process nearly became a verification.** The judge
  image's first run failed to bind a port already held by the verify instance,
  and the probes after it answered from that instance instead. Told in full
  under the judge instance above. The lesson is narrow and worth keeping:
  **`/health` identifies a listener, not an image.** Every probe in that
  section reports something only the intended build could say.
- **The failure ledger was reported as "3 failed" when two things failed.** My
  guard counted rows in `failures`; the system deliberately records one event at
  two levels. Correct as a gate, wrong as a number, and mine.

## State left on the machine

| | |
|---|---|
| `~/second-shift` | production, **untouched by this session**, still the 17 Oct branch tree, API serving, schema 4 |
| `~/second-shift-src` | the session clone, now **detached at `origin/main`**. No branch ref was moved; its `endgame/finish-openspec` ref still points where it did |
| `~/smoke-2026-10-27/` | the throwaway snapshot, its payload tree, the run scripts and every log. Safe to delete |
| `~/second-shift-restore-test` | still present from 16 Oct. Still safe to delete |
| `~/second-shift-data/payloads` | **new.** Created by this session's runs; did not exist before |
| NAS | backups under a `second-shift-backups` directory on the `scratch` share. **18 of them**, newest 0.0 days old, on another device |
| `~/second-shift-verify` | the seeded throwaway and the brain clone from the sample-data work. Its API on 8090 was **stopped** — it is what answered the judge image's probes by mistake |
| `second-shift-judge:2026-10-27` | the image built tonight, **retained**. Its container was removed after the probes |
| `~/smoke-2026-10-27/gates3.sh`, `judge-image.sh` | the two scripts behind the gate table and the image build |
| **The reasoner is running without speculative decoding** | The drop-in at `~/.config/systemd/user/second-shift-reasoner.service.d/no-spec-decode.conf` is still active, and it carries its own removal instructions |

**The drop-in was deliberately left in place.** Removing it restores a
configuration that took an illegal CUDA memory access twelve samples into a run
today. Restoring it is a choice somebody should make deliberately, with the
knowledge that `judge_model_version` cannot tell the two apart afterward — and
the week-9 retry, if there is one, is better off without it.

**`doctor` on production at the end of the session: all 8 checks passed, exit
0.** Nothing this session did left that machine worse than it found it.

---

## Still open from 16 Oct, and not this session's to close

- **The NAS has no backup share.** Every captured idea still sits under
  `scratch`, a volume whose name says it is disposable — and as of this session
  that archive carries the payload tree as well, which is the thing the 16 Oct
  report said should happen before payloads landed there. It did not happen
  first. Still a decision, not a task.
- **The judge image is `arm64`** and needs a cross-build before it is deployed
  anywhere. Not attempted here.
- **The demo night returns `outcome: null`.** Not attempted here.

---

## What I would do with the remaining three days

Three days. In priority order, with the reason each sits where it does — none of
these is a decision this session made.

| # | Item | Source | Blocked on | Why here |
|---|---|---|---|---|
| 1 | Push the branch holding `0004_external_keys.sql`, `providers/tokenfactory.py` and `telemetry/reports.py` to a remote | *Where that unpushed work actually lives*, above | **The subject.** Public repository; the no-environment gate has never run on that branch | It is one command, and until it runs a disk failure costs the schema the live database is on. Everything else here assumes the machine survives the week |
| 2 | A top-up path in `score`, so a run can be completed rather than regenerated | New; needs a change of its own | Nothing | The submission's centerpiece number is unobtainable without it. Two runs are already burned, 3 of 18 and 16 of 18, and week 1 needs a clean 18 at roughly one-in-three odds |
| 3 | `close_run` at the end of `generate_night` | *The demo night's `outcome: null`* | Nothing | One call. It is the first thing a hackathon judge sees, and it fixes the judge image as a side effect |
| 4 | Queue an idea, run one real night | `2026-09-17-the-night-revises-what-it-believes` task 2.1 | An idea being captured — which is the subject's, not a session's | Closes step 5 and the last open task of a change sitting at 6 of 7. The night is the product; nothing has exercised it on real data since 17 Sep |
| 5 | The reboot | `RECOVERY.md`, *what a machine session still owes* | **Somebody at the machine.** It cannot be done over SSH | Still the only item from 16 Oct that nobody has closed, and the capability-caching finding below makes its outcome predictable rather than unknown |
| 6 | Confirm the judge deployment's architecture, then cross-build | ADR 0009 | The Nebius console, which needs a credential | Ten minutes of checking that decides whether the demo can be deployed at all. The ADR should have recorded it and does not |
| 7 | Thread `environment` through `local_reasoner_settings()` | *Both failures are one defect* | Nothing | Two tests of 930 cannot pass on the one machine that runs the reasoner, and the defect is in resolution rather than in the tests |
| 8 | Archive `retain-model-call-payloads` | `openspec list` | Nothing | 17 of 17, and tonight is its first end-to-end evidence: 36 payload rows, `output_path` 18/18, a 70-file payload tree in a verified backup |

**Not on this list, deliberately:** raising `reasoner_max_tokens` a third time.
It was 4096, then 16000, and the architect still ran to the cap once in 18 on
the prompt that also drew the judge refusal. A larger budget buys a longer
version of the same behavior, and the prompt is the thing to look at.

### Every non-archived OpenSpec change

From the repository-local `openspec list --json`, with remaining task IDs read
from each `tasks.md`. **This is task completion, not production readiness.**

| Change | Done / total | Complete | Remaining | Remaining task IDs |
|---|---|---|---|---|
| `retain-model-call-payloads` | 17 / 17 | **100.0%** | 0 | — ready to archive |
| `2026-09-17-the-night-revises-what-it-believes` | 6 / 7 | **85.7%** | 1 | `2.1` a real night proposes a belief against the real brain and the diff is read — needs an idea queued |
| `2026-09-02-add-nebius-executor` | 3 / 23 | **13.0%** | 20 | `2.1.1`–`2.1.5` telemetry collection from a job's written form, parents-first, idempotent, absent-telemetry handling; `2.2.1`–`2.2.7` the `NebiusExecutor`, credentials from the machine's secrets file, `local-only` refused at the call, policy-filtered context only, a real fan-out, a job that never returns, remote telemetry rejoining the tree; `2.3.1`–`2.3.3` a Token Factory `Reasoner`, standard rates, cloud-night cost readable from `model_calls`; `2.4.1`–`2.4.5` the five acceptance runs and `scripts/gate.py` green |

The counts agree with the task files; nothing here is unverified. `openspec` is
not installed on the always-on machine, so this was read on the laptop against
the same commit.

**`add-nebius-executor` is 20 tasks and a credential away, and it is the source
of both remaining "Not run" rows in `docs/SUBMISSION.md`.** Three days is not
that. Saying so now is more useful than discovering it on the 30th.
