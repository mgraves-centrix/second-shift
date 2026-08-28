# Overnight prompt

Paste as the first message of a fresh session. It runs unattended until the work
queue is done or every remaining item is blocked.

---

You are working unattended overnight on Second Shift. I am asleep. I will read
your report in the morning.

Read `openspec/constitution.md`, `CLAUDE.md`, and `docs/SPEC_ROADMAP.md` before
touching anything. They are not background; they are the rules you are working
under.

## The one thing that must not happen

**I am dogfooding on this machine.** The capture API is live and taking real
ideas. Breaking it costs me captures that cannot be recovered, and that is worse
than shipping nothing tonight.

Before you finish, and after any deployment, prove capture still works:

```bash
curl -sf https://<host>.<tailnet>.ts.net/health
curl -sf https://<host>.<tailnet>.ts.net/capabilities | head -5
ssh <spark> 'cd ~/second-shift/apps/api && ./.venv/bin/python -m secondshift.brain --status'
```

If capture is broken and you cannot fix it in ten minutes, **revert to the last
known-good commit, redeploy, verify, and stop.** A working system and an
unfinished feature beats a broken system and a finished one.

## Work queue

Take these in order. Finish one completely — proposed, applied, verified,
archived, merged — before starting the next. A half-finished capability is worth
less than none, because it looks done.

1. **`configuration`** — settings are scattered across three TOML files and
   eight environment variables with no single place to look, and adding a
   fourth would make it worse. Consolidate into one documented, discoverable
   surface with precedence rules (environment overrides file, file overrides
   default), and a way to print the resolved configuration and where each value
   came from. Include **voice** and **brain location** as first-class settings.

   Voice is a placeholder with no implementation behind it: TTS is unverified on
   this hardware and which voices exist is unknown until the week-3 spike. Model
   the setting so that landing TTS is data entry, and make an unset or unusable
   voice degrade to text rather than failing — text-first is a constitution
   principle, and a briefing that will not render because a voice is missing
   violates it.

   Migrating existing settings must not break the running deployment. Old names
   keep working, or you migrate every reference and prove it on the machine.

2. **`synthetic-seed`** — the night generator. Fully unblocked, needs nothing
   from me, and unblocks every piece of frontend work. A night scrubber cannot
   be built against four real events. Generate a full night: six hours, 400+
   events across lanes, a nested invocation tree, model calls with realistic
   costs and latencies, several build variants in a variant group. Every row
   `is_synthetic = 1`.

3. **`evals`** — the measurement spine, minus the content. I am choosing the
   five prompts and correcting `profile.md` in the morning, so **build the
   machinery and leave the prompts as data**: the runner, the scoring path, the
   `eval_runs`/`eval_results` writes, three samples per prompt, judge model and
   `rubric_sha` pinned, scored against a recorded `brain_sha` rather than HEAD.
   Seed it with the ten candidates in `config/evals/candidates.md` marked as
   unselected, so swapping in five is data entry and not code.

4. **`nebius-executor`** — only if the rest are done and you have more than two
   hours. It carries every deferred obligation and needs credentials I may not
   have configured. Check for credentials first; if absent, **do not stub it** —
   write the proposal and stop there, so the morning starts with a reviewed plan
   rather than fake code.

If an item is blocked, move to the next and record why. Do not sit waiting.

## Hard stops — no exceptions

Stop, record the question, and move to the next item:

- **A clarification marker.** Do not answer your own markers. Do not pick the
  obvious default. The gate exists because the answer changes the work, and a
  marker resolved by assumption launders a guess into a recorded decision. Put
  it in the morning report with your recommendation and reasoning.
- **A constitution violation.** Blocking, not advisory.
- **Anything in `NOT_BUILDING.md`.** Refuse and record.
- **Credentials, payment, account settings, or anything outward-facing** beyond
  pushing to this repository.
- **Rewriting published history**, force-pushing, or deleting anything I have
  not already agreed to delete.
Restarting `nemotron-lightning` is permitted. It takes about three minutes to
reload, so do it deliberately and confirm it is serving again before relying on
it — the capability probe reports `local_reasoner` unavailable during the window,
which is correct but will make anything that checks look degraded.

## The loop, with the commands

### Before starting anything

```bash
git -C . status --short && git -C . log --oneline -1
openspec list && openspec list --specs
apps/api/.venv/bin/python -m pytest apps/api/tests -q
npm --prefix apps/web run test
openspec validate --specs --strict
scripts/check-no-environment.sh
scripts/check-american-english.sh
```

All must pass. A red suite before you start means you cannot tell what you broke.

### Per capability

```bash
git checkout -b overnight/<capability>
openspec new change add-<capability>
```

Write `proposal.md`, `design.md` (L3 only), `specs/<capability>/spec.md`,
`tasks.md`. Then:

```bash
openspec validate add-<capability> --strict
git add -A && git commit -m "Propose add-<capability>: <what and why>"
```

**If markers exist, stop here for this capability.** Commit the proposal, push
the branch, record the questions, move to the next item.

If none:

```bash
openspec instructions apply --change add-<capability> --json
```

Work tasks in order. Commit per task group, not per task and not at the end.
Mark `- [x]` only when the specified behavior is genuinely implemented.

### Verify — all of it, every time

```bash
apps/api/.venv/bin/python -m pytest apps/api/tests -q
npm --prefix apps/web run test
openspec validate add-<capability> --strict
scripts/check-no-environment.sh
scripts/check-american-english.sh

# on the target machine, which is where two defects have already hidden
SPARK_HOST=<host> SPARK_USER=<user> ./deploy/spark/deploy.sh
ssh <spark> 'cd ~/second-shift/apps/api && ./.venv/bin/python -m pytest tests -q'
```

Python there is 3.12 and the architecture is aarch64; local dev is neither.
`COPYFILE_DISABLE=1` on any transfer — macOS AppleDouble sidecars break
migration discovery and the source scan. **Never `uv run` on that machine.**

### Archive and merge

Sync deltas into canonical specs, then **verify requirement by requirement
before anything moves**, and gate on the result:

```bash
# the verification must exit non-zero on mismatch, and you must not proceed past it
openspec validate --specs --strict
```

If verification fails, fix it and re-verify. Do not archive on a failed check —
that has happened once already and it silently dropped a requirement.

```bash
git mv openspec/changes/add-<capability> openspec/changes/archive/$(date +%F)-add-<capability>
git add -A && git commit -m "Archive add-<capability>; sync into canonical specs"
git checkout main && git merge --no-ff overnight/<capability> -m "Merge overnight/<capability>"
git push origin main
git branch -d overnight/<capability>
```

`--no-ff` deliberately: an overnight capability should be one revertable unit in
the history, not a scatter of commits I have to reconstruct.

## Quality bar

The code is the submission. Judges read this repository.

**Never ship:** a `TODO`; a function returning a plausible constant instead of
doing the work; a test that still passes with the implementation deleted; a mock
of the thing under test; a broad `except` that exists to make a test green; a
docstring restating the signature; an API you have not verified exists; a task
marked `[x]` that is not done.

**Always:** match the surrounding idiom so new code is unidentifiable as new;
write the test that would have caught the bug; prefer the boring construction;
name a non-obvious trade-off in a comment; keep provider specifics inside
`providers/`; keep writes inside the recorder's lock; keep tables append-only;
let failures be loud.

American English. No hostnames, addresses, usernames or home paths in tracked
files — use placeholders; both check scripts must pass before every merge.

## Use agents, in parallel, without letting them collide

Run as much concurrently as the work genuinely allows. Launch independent agents
in a single message so they run at the same time.

**Read-only agents are always safe in parallel.** Surveys, adversarial
pre-reviews, spec critiques, source scans. Use several at once and use them
freely — the adversarial pre-review has already earned its place twice, finding
four defects in shipped code before `capture`, and nine environment variables
where the plan said eight before `configuration`.

**Writing agents must own disjoint files.** Two agents editing the same module
produce a merge you did not ask for and cannot review. Before delegating any
implementation, decide the file ownership and state it in the agent's prompt:
"you own `packages/seed/**` and `apps/api/tests/test_seed.py`; touch nothing
else." If two pieces of work cannot be given disjoint ownership, they are not
parallel work — do them yourself, in order.

**Use `isolation: "worktree"`** for any agent that writes, so it works in its own
checkout and cannot see or clobber another's in-progress edits. Merge its branch
yourself once you have reviewed the diff against the spec.

**Sequence by shared surface, parallelize by new surface.** A refactor of
existing shared modules is sequential work: `config.py`, `pricing.py`,
`repo.py`, `main.py` are read by everything, and concurrent edits there conflict
by construction. A capability that lives in a new package is parallel work.
Land the shared refactor first, then fan out.

**Do not delegate:** the airlock, the telemetry recorder, migrations, the
argument in a proposal, or anything touching the running deployment. Review
everything an agent returns against the spec before merging it — its output is a
draft, and you are accountable for it.

## Morning report

End with this, and nothing else:

1. **What shipped** — capabilities archived and merged, with test counts.
2. **What is blocked, and on what** — every clarification marker in full, with
   your recommendation and the reasoning behind it, so I can answer over
   coffee without rereading anything.
3. **What you found** — defects, surprises, anything that changes the plan.
   Findings in shipped code matter more than features; say them first.
4. **System state** — capture verified working, brain backlog, test counts on
   both machines, whether anything was deployed.
5. **What you would do next**, and why that rather than the alternative.

Be honest about failures. A report that says "three of five tasks, blocked on X,
here is exactly what I need" is worth more than one that says everything went
well. If you broke something and fixed it, say so — the fix is the interesting
part.
