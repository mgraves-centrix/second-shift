# Artifacts prompt

Paste as the first message of a fresh session. Local; the Spark to produce real
ones.

**Depends on `NIGHT_PIPELINE.md`, which shipped 2 Sep. Runs in parallel with
`RESEARCH.md`; the two must not both be in `secondshift/night/`.**

---

Build `artifacts`. Read `openspec/constitution.md`, `CLAUDE.md`,
`docs/decisions/0004-nebius-workload-split.md` and `docs/SPEC_ROADMAP.md` first;
they are the rules, not background.

## Why this one

"Idea in, artifact out, memory in between" is the scope boundary, and the middle
term does not exist. The night can run stages; nothing lands a file you can open.

This is also where the Nebius argument becomes real rather than decorative. ADR
0004 makes parallel variant generation the strongest available use of Serverless
Jobs precisely because it is the thing the Spark **cannot** do — one box cannot
run five builds concurrently at speed. The parallelism is why the artifact is
better, and `variant_group` / `variant_rank` have been in the schema since day 1
with nothing writing them.

## What already exists — do not invent any of it

- `artifacts`: `kind` CHECK over `brief`, `research_digest`, `mockup`, `build`,
  `critique`, `summary`; `variant_group`; `variant_index`; `variant_rank`;
  `path`; `content_sha`; `bytes`; `produced_by_invocation_id`. Six kinds, fixed.
- `Repository.insert_artifact(...)` exists — added when the seed generator needed
  it, and the commit that added it noted the proposal had wrongly claimed nothing
  was needed. It is there; use it.
- `outcomes`: `label` CHECK over `keep`, `kill`, `revise` (explicit judgement)
  and `signal` CHECK over `opened`, `iterated`, `used`, `exported`, `ignored`
  (implicit), with a CHECK that at least one is present. Nothing writes it.
- **The synthetic night already writes artifacts with shuffled ranks**, and the
  commit says why: *a renderer that assumes rank equals index is wrong on this
  data. That is the point of generating it.* Your ranking must survive that.
- `cost_per_accepted_artifact` is an existing view. "Accepted" is defined by
  `outcomes`, which is why outcome capture is part of this capability and not a
  later nicety.

## The open decision

**What ranking means when the critic is one model reading its own family's
output.**

ADR 0004 has the critic rank variants into a `variant_group`. That is settled.
What is not settled is whether a rank is trustworthy — the same model family
generates and judges, and `variant_rank` feeds `cost_per_accepted_artifact`,
which is a scored chart.

**Do not decide this by preference.** Generate five real variants of one real
brief on the Spark, rank them, and then read them yourself. Report whether the
ranking matches your own ordering. If it does not, say so plainly and propose
what the rank should be used for instead — a rank nobody trusts is worse than no
rank, because it looks like evidence.

> **This cannot be answered without the machine, and it must not be faked.** The
> Spark has been unreachable since 2 Sep. Variants generated against the `cloud`
> profile's `EchoReasoner` are placeholders, so ranking them measures nothing and
> a comparison written from them would be exactly the untrustworthy evidence this
> section warns about. Build the machinery, make the *structure* verifiable —
> rank is not index, the group id is stable, the three fields are never
> conflated — and leave the trust question open with a recommendation. Answer it
> when the machine returns.

The second open thing: **where artifacts live on disk.** `path` is a column, not
a directory layout. Decide the layout with the judge instance in mind — it must
hold artifacts that contain zero real data.

## What good looks like

- An artifact is a **file you can open in the tool that edits that kind of file**.
  A brief is markdown. A mockup is HTML. A build is a directory.
  `NOT_BUILDING.md` excludes editing artifacts in-app precisely so this stays
  true.
- `content_sha` and `bytes` are computed from what actually landed, so a
  truncated write is detectable.
- Every artifact names the invocation that produced it, so the scrubber can go
  from a mark on the timeline to a file on disk.
- A variant group has a stable group id, indices that identify each variant, and
  ranks that are the critic's ordering — three different things, never conflated.
- An outcome can be recorded against an artifact, and
  `cost_per_accepted_artifact` returns a real number afterward.
- A run that produced three of five variants still presents three. Principle 3.

## Scope — what NOT to build

- **Nothing executes a generated build.** `NOT_BUILDING.md` excludes autonomous
  execution of generated code — sandboxing an arbitrary executor is a project,
  not a feature. Produce it; do not run it.
- **No in-app editing.** Artifacts land as files.
- **No new artifact kinds.** Six, fixed by a database CHECK.
- **No Nebius fan-out here.** This defines what a variant is and how it is
  ranked; `NEBIUS_EXECUTOR.md` makes them parallel. Build it so the fan-out is a
  substitution, not a rewrite.
- **No outcome-capture UI.** The recording path, not the interface.

## Constitution hooks

- **Principle 6 governs the boundary.** An artifact system that grows a status,
  an assignee or a due date has become task management. It has a path, a kind and
  an outcome.
- **Principle 3.** Each variant commits as it completes. A fan-out where one
  variant's failure loses the other four is the violation.
- **Principle 5.** The judge instance runs this same code with `is_synthetic = 1`
  throughout, so nothing here may assume real data.
- **Principle 7.** Every artifact names its producing invocation; the cost views
  exclude synthetic rows.

## The loop

```bash
git status --short && openspec list && openspec list --specs
apps/api/.venv/bin/python -m pytest apps/api/tests -q          # 431 pass today
npm --prefix apps/web run test && npm --prefix apps/web run typecheck
scripts/check-no-environment.sh && scripts/check-american-english.sh
```

All green before starting. Then propose, clarify, apply, verify, sync, archive.

## Verification

- **Rank is not index.** Assert against the synthetic night, whose ranks are a
  shuffled permutation on purpose. **Prove the test can fail:** replace the
  critic's rank with the generation index and watch it go red. A test that stays
  green there is testing nothing.
- A partial fan-out records what completed and the run is `degraded`, not lost.
- `content_sha` matches the bytes on disk; corrupt the file and the check fails.
- An artifact resolves to its producing invocation and back.
- Recording an outcome makes `cost_per_accepted_artifact` return a number, and
  synthetic rows are excluded from it.
- **Then produce a real brief on the Spark and read it.** Paste it in the
  report. (The "three entries queued since 28 Aug" this line used to name were
  read off the machine on 2 Sep and have not been re-read since — query it
  rather than quoting that.)

## Quality bar

The code is the submission. Judges read this repository.

**Never ship:** a `TODO`; an artifact writer that returns a plausible path
without writing bytes; a test that passes with the implementation deleted; lorem
text; a ranking that is really the generation order; a build stage that executes
its output.

**Always:** match the surrounding idiom; write the test that would have caught
the bug; keep tables append-only; let failures be loud. American English. No
hostnames, addresses, usernames or home paths in tracked files.

## Hard stops

Stop, record the question with your recommendation, and move on:

- A `[NEEDS CLARIFICATION]` marker. Do not answer your own.
- A constitution violation. Blocking, not advisory.
- Anything in `NOT_BUILDING.md` — and "run the build to check it works" is over
  that line.
- Credentials, payment, account settings, or anything outward-facing.
- Rewriting published history or force-pushing.

## Report

1. The five real variants, your own ranking, the critic's ranking, and whether
   they agree. If they do not, say so — that is the finding.
2. The on-disk layout, and why it works for the judge instance.
3. What shipped, with test counts.
4. One real brief, pasted. If it is not worth reading, say so; a pipeline that
   produces unreadable artifacts is a finding, not a milestone.
5. Anything blocked, with your recommendation.
6. What you would do next, and why that rather than the alternative.
