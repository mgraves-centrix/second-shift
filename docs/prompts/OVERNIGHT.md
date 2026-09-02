# Overnight prompt

Paste as the first message of a fresh session. It runs unattended until every
unblocked item is shipped or every remaining item is blocked — never until a
fixed list is empty, because a fixed list goes stale.

**This is the one prompt in this directory allowed to reference the others.**
Every other prompt is self-contained on purpose. This one's job is orchestration
— deciding what to work on and in what order — so its content is instructions
for *finding and following* the right document, not a substitute for it. When
this prompt tells you to read `RETRIEVAL.md`, that is not a suggestion; the
capability prompt is the ground truth for that capability, and this document is
not.

---

You are working unattended overnight on Second Shift. I am asleep. I will read
your report in the morning.

Read `openspec/constitution.md` and `CLAUDE.md` before touching anything. They
are not background; they are the rules you are working under, for every item
you touch tonight, not just the first one.

## Why a dated snapshot cannot be trusted, including this one

`docs/prompts/00_INDEX.md` carries a table titled "What is true on 2 Sep." Hours
after it was written, in the same session, three of its rows were already
wrong: Nebius credentials went from absent to live, `nebius-executor`'s first
task group went from unresolved to closed, and `retrieval` went from unshipped
to in progress. Nobody edited that table maliciously — it was accurate the
moment it was written and stale within hours, because it is a photograph, not a
query.

This prompt contains no such table, deliberately. Anywhere you need to know
what is shipped, what is active, or what a capability's schema looks like
today, the instruction below is to **run the query**, not to read a number some
earlier session wrote down. Treat every fact in every document — this one
included — as a claim to verify against the repository and the machine, not a
fact to inherit. That includes facts in `docs/SPEC_ROADMAP.md`: it is the best
available record, and it has been wrong before (the week-1 eval baseline it
once reported never existed).

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

## What to work on, determined live, never from memory

Do not carry over what a previous overnight session was working on unless you
have checked it is still true. In order:

1. `openspec list` — an active, unarchived change exists and is not marked
   complete. **Resume it.** Read its `tasks.md` for exactly where it stopped;
   do not re-propose or restart what is already argued.
2. If nothing is active: read `docs/SPEC_ROADMAP.md`'s roadmap tables fresh.
   Take the first entry with no "shipped" heading and no accepted-but-unshipped
   status. Its **Decided** lines are settled; do not re-derive them. Its
   **Open** lines are markers waiting to be asked, not assumptions waiting to
   be made.
3. Cross-check against `docs/prompts/00_INDEX.md`'s dependency table and its
   named collision surfaces before starting. Two sessions — and two nights —
   must never both write to `apps/web/app/`, `secondshift/night/`, or
   `api/app.py`. If the capability you picked shares a surface with something
   already in flight, it is not tonight's item; pick the next one down the
   list that is genuinely disjoint.
4. A prompt file exists in `docs/prompts/` for most roadmap capabilities.
   **Open it and follow it.** Its "why this one," "what already exists," and
   "scope — what not to build" sections are the brief. This document tells you
   which capability; that document tells you how.
5. Some prompt files — `CONFIGURATION.md`, `API_LAYER.md`, `TEST_HARNESS.md`,
   `OPERATIONS.md`, `ASR.md`, `EVAL_SCORING.md` — describe real, documented
   gaps that have no entry in `docs/SPEC_ROADMAP.md`'s capability tables. **The
   open decision** for these is how much process ceremony each one earns — a
   configuration cleanup and a new capability are not the same shape of change,
   and this document does not decide that by preference. `openspec/config.yaml`
   already classifies scale (L0–L4) and gates process to it; run
   `/opsx:propose` and let it classify the work rather than assuming every item
   needs a design doc and an ADR, or that none of them do.
6. If truly nothing is unblocked — everything shippable is shipped, and every
   remaining item is blocked on a marker, a credential, or another session —
   stop, write the report below, and do not manufacture work to fill the night.

## Ground every line in documentation, not memory

This is not a style preference. Twice in this project's history, a plausible
assumption was committed and later found wrong by someone who actually read the
source: a claim that Nebius Serverless Endpoints could only serve models, not
applications (`ADR 0009` corrects it), and a week-1 eval baseline that was
recorded as existing when `eval_runs` held zero rows (`docs/SPEC_ROADMAP.md`'s
evals entry corrects it). Both were caught, both cost time that reading first
would not have.

So, for whatever you picked above:

- Read the capability's own prompt file if one exists, in full, before writing
  anything. Its "what already exists" section is what you build from — **do not
  invent any of it.** If it cites an interface, open the interface's actual
  source file and confirm the signature before calling it; an invented method
  name is the most expensive kind of mistake because it looks right in review.
- Read the ADRs the roadmap entry or the prompt file cites. An ADR is a
  decision already made; treat it as a constraint, not a suggestion to
  re-litigate.
- Read `docs/DATA_MODEL.md` and the actual migration files before writing SQL.
  The migrations directory is the schema's authority, not this document, not
  `docs/ARCHITECTURE.md`'s prose summary of it.
- When a fact is checkable on the running machine — a row count, a live
  response shape, whether a service is up — check it there. A number copied
  from a document is a claim about the document, not about the system.

## What good looks like

A night where every capability touched is either fully archived — proposed,
clarified, applied, verified, synced, merged — or stopped at a named,
answerable question, never left half-implemented and marked as if it were
further along than it is. A morning report where every claim in it was true at
the moment it was written, because it was checked at that moment, not carried
forward from an earlier assumption. Capture working when I wake up, verified,
not assumed.

## Scope — what not to build

- Nothing in `NOT_BUILDING.md`. Its override protocol requires a human decision
  naming the trade-off; an unattended session cannot make that trade for me.
- No capability this document or the roadmap does not name. An idea for
  something adjacent and useful is a line in the morning report, not a branch.
- No stub standing in for a capability blocked on something you do not have —
  a stub that returns plausible data is worse than an honest gap, because it is
  indistinguishable from the real thing in the numbers this submission is
  measured on.
- No new credential, account, or payment method, provisioned on your own
  initiative. A credential that **already exists** on the always-on machine —
  today that includes both a Tavily key and the Nebius Token Factory and Cloud
  IAM credentials, at `~/.config/second-shift/secrets.env` and
  `~/.config/second-shift/keys/`, mode 0600, outside any tracked path — is not
  a new credential decision. Fetch it over the tailnet the same way every other
  read from that machine happens; do not copy it into this repository or any
  log you write. Provisioning a new one is still a hard stop below.

## Constitution hooks

Every capability tonight gets checked against all seven; these are the ones
most likely to be the sharp edge, by what you are likely to be doing:

- **Principle 2, the Privacy Airlock**, on anything touching retrieval,
  research, or a cloud provider call. The sharpest test in the codebase: a
  `local-only` entry's content must never appear in anything eligible for
  egress, and the guard is a `CHECK` constraint, not a convention.
- **Principle 3, no empty mornings**, on anything touching the night pipeline
  or stage machine. A stage that holds its output until the run completes is a
  violation regardless of how the tests read.
- **Principle 5, one codebase, two deployments**, on anything touching a
  provider. Provider specifics stay inside `providers/`; the night pipeline and
  the API see only the interface.
- **Principle 7, telemetry from line one**, on every agent invocation and every
  model call, including ones made while testing. A call that returns without
  writing `model_calls` is not caught by any test that mocks the provider.

A violation is blocking, not advisory, per the constitution's own text — stop,
do not implement around it, and record it in the report.

## Hard stops — no exceptions

Stop, record the question, and move to the next item:

- **A `[NEEDS CLARIFICATION]` marker.** Do not answer your own markers. Do not
  pick the obvious default. The gate exists because the answer changes the
  work, and a marker resolved by assumption launders a guess into a recorded
  decision. Put it in the morning report with your recommendation and
  reasoning.
- **A constitution violation.** Blocking, not advisory.
- **Anything in `NOT_BUILDING.md`.**
- **Provisioning a new credential, payment method, or account**, or any action
  outward-facing beyond pushing to this repository and reading credentials
  that already exist on the always-on machine, as scoped above.
- **Rewriting published history**, force-pushing, or deleting anything I have
  not already agreed to delete.

Restarting `nemotron-lightning` is permitted. It takes about three minutes to
reload, so do it deliberately and confirm it is serving again before relying on
it — the capability probe reports `local_reasoner` unavailable during the
window, which is correct but will make anything that checks look degraded.

## The loop, with the commands

### Before starting anything

```bash
git status --short && git log --oneline -1
openspec list && openspec list --specs
apps/api/.venv/bin/python -m pytest apps/api/tests -q
npm --prefix apps/web run test && npm --prefix apps/web run typecheck
openspec validate --specs --strict
scripts/check-no-environment.sh
scripts/check-american-english.sh
```

All must pass before you touch anything. A red suite before you start means you
cannot tell what you broke.

### Per capability

Prefer `/ship-capability <name>` — it already encodes preconditions, the
propose/clarify/apply/verify/sync/archive phases, the Spark verification step,
and the commit-and-push boundaries, and reusing it means this document cannot
drift out of sync with that process the way the old version of this prompt
drifted out of sync with the roadmap it hardcoded. Follow its clarification
gate exactly: if markers exist, stop for that capability, commit the proposal,
and move to the next unblocked item. Do not wait idle for an answer that will
not come before morning.

For a gap with no roadmap entry (§ "What to work on," item 5), the equivalent
manual sequence is `/opsx:propose`, then `/openspec:clarify` if markers exist
and stop there, then `/opsx:apply`, then the verification below, then
`/opsx:archive`.

### Verify — all of it, every time

```bash
apps/api/.venv/bin/python -m pytest apps/api/tests -q
npm --prefix apps/web run test
openspec validate <change> --strict
scripts/check-no-environment.sh
scripts/check-american-english.sh

# on the target machine, which is where defects have already hidden twice
SPARK_HOST=<host> SPARK_USER=<user> ./deploy/spark/deploy.sh
ssh <spark> 'cd ~/second-shift/apps/api && ./.venv/bin/python -m pytest tests -q'
```

Python there is 3.12 and the architecture is aarch64; local dev is neither.
`COPYFILE_DISABLE=1` on any transfer — macOS AppleDouble sidecars break
migration discovery and the source scan. **Never `uv run` on that machine.**

Exercise the capability against reality, not only its unit suite, wherever it
has a real-world surface — the live capability probe, an actual endpoint, a
real file round-trip. A green unit suite is evidence the code does what the
tests assert, not evidence the tests assert the right thing.

**For the one test this capability's argument actually rests on, prove it can
fail before trusting that it passes.** Comment out the guard, delete the
filter, hardcode the value the check exists to catch — then run the suite and
confirm it goes red. Only then put the real code back and confirm it goes
green again. A test this session has already produced this way: `retrieval`'s
airlock check is required to be demonstrated failing with the policy filter
removed, not merely asserted passing with it in place. A passing suite is not
by itself proof of anything — `night-timeline` shipped with every automated
check green while the playhead sat motionless at the wrong position, because
every check read the ARIA value rather than where the element actually
rendered. Only a screenshot caught it. Read what a check actually measures,
not just whether it is green.

### Archive

Sync deltas into canonical specs, then verify requirement by requirement before
anything moves — `openspec validate --specs --strict` must exit non-zero on a
mismatch, and you must not proceed past a failure. Archiving on a failed check
has already silently dropped a requirement once.

Before archiving, ask the question the archive step exists to ask: did this
change establish an architectural decision that lives only in `design.md`?
That file is about to move out of the discoverable path. If yes, write the ADR
first, as its own numbered file — never by editing an existing one that a later
reader needs to see was superseded, not silently corrected.

Commit and push at phase ends, never mid-phase with a red suite.

## Quality bar

The code is the submission. Judges read this repository.

**Never ship:** a `TODO`; a function returning a plausible constant instead of
doing the work; a test that still passes with the implementation deleted; a
mock of the thing under test; a broad `except` that exists to make a test
green; a docstring restating the signature; an API you have not verified
exists; a task marked `[x]` that is not done.

**Always:** match the surrounding idiom so new code is unidentifiable as new;
write the test that would have caught the bug; prefer the boring construction;
name a non-obvious trade-off in a comment; keep provider specifics inside
`providers/`; keep writes inside the recorder's lock; keep tables append-only;
let failures be loud.

American English. No hostnames, addresses, usernames or home paths in tracked
files — use placeholders; both check scripts must pass before every merge.

## Use agents, in parallel, without letting them collide

Run as much concurrently as the work genuinely allows. Launch independent
agents in a single message so they run at the same time.

**Read-only agents are always safe in parallel.** Surveys of unfamiliar code,
adversarial pre-reviews, spec critiques. Use them before writing anything
non-trivial — a survey that costs minutes has already found defects that would
otherwise have shipped.

**Writing agents must own disjoint files.** Two agents editing the same module
produce a merge you did not ask for and cannot review. Before delegating any
implementation, decide file ownership and state it in the agent's prompt
explicitly: which paths it owns, and that it touches nothing else.

**Use `isolation: "worktree"`** for any agent that writes, so it works in its
own checkout and cannot see or clobber another's in-progress edits. Merge its
branch yourself once you have reviewed the diff against the spec.

**Sequence by shared surface, parallelize by new surface.** `config.py`,
`db/repository.py`, `api/app.py` are read by everything; concurrent edits there
conflict by construction. A capability living in a new package is parallel
work.

**Do not delegate:** the airlock, the telemetry recorder, migrations, the
argument in a proposal, or anything touching the running deployment. Review
everything an agent returns against the spec before merging it — its output is
a draft, and you are accountable for it.

## Morning report

End with this, and nothing else:

1. **What shipped** — capabilities archived and merged, with test counts.
2. **What is blocked, and on what** — every clarification marker in full, with
   your recommendation and the reasoning behind it, so I can answer over coffee
   without rereading anything.
3. **What you found** — defects, surprises, anything that changes the plan.
   Findings in shipped code matter more than features; say them first.
4. **What you read to ground each piece of work** — which prompt file, which
   ADRs, which source files you opened to confirm a signature before calling
   it. Not because I will check all of it, but because writing this list is
   what stops the shortcut of skipping the reading.
5. **System state** — capture verified working, brain backlog, test counts on
   both machines, whether anything was deployed.
6. **What you would do next**, and why that rather than the alternative.

Be honest about failures. A report that says "one of three shipped, blocked on
X, here is exactly what I need" is worth more than one that says everything
went well. If you broke something and fixed it, say so — the fix is the
interesting part.
