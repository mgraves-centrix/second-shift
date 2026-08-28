---
name: "Next"
description: Orient on current state, show the work stack, and start the next item — routing to the capability flow or the spike protocol as appropriate.
category: Workflow
tags: [workflow, planning, spike]
---

Work out what is next, show the stack, and start it.

Week one is two kinds of work and they need different handling. **Capabilities**
go through the spec flow. **Spikes** are timeboxed experiments against unproven
hardware and services — they have a pass gate and an abort ladder, and no spec
ceremony at all. Confusing the two is how a half-day investigation eats a day
and a half.

Optional argument names an item (`/next spike-b`, `/next capture`). Without one,
take what the plan says is due.

---

## 1. Orient

Report each in one line. Do not proceed past a failure — fix it or say why it is
acceptable.

```
date "+%Y-%m-%d %a"
git status --short && git log --oneline -1
openspec list && openspec list --specs
apps/api/.venv/bin/python -m pytest apps/api/tests -q
```

Then read `docs/WEEK_ONE.md` for the day that matches today's date, and
`docs/SPEC_ROADMAP.md` for the capability queue.

**Consult the failure ledger before planning anything.** The constitution says
it is read at planning time; this is the only place that actually happens.

```sql
SELECT type, signature, recurrence_count, latest_resolution FROM failure_ledger
ORDER BY recurrence_count DESC;
```

If the work ahead resembles a recorded failure, say so and apply the resolution
before repeating the mistake. A ledger nothing reads is a log.

## 2. Show the stack

Three to five lines, no more:

- **Now** — the item being started, and which kind it is.
- **Blocked** — anything waiting on a decision or an unfinished spike, naming
  what would unblock it.
- **Next** — the two items after this one.
- **Slipping** — anything whose day has passed. Say it plainly rather than
  quietly re-planning around it.

If the plan says one thing and reality says another, believe reality and revise
`docs/WEEK_ONE.md` before starting.

## 3. Route

**Capability** — something with a roadmap entry, requirements and tests, that
ends up in `openspec/specs/`. Invoke `/ship-capability <name>` and follow it.
Nothing more to do here.

**Spike** — a timeboxed question about unproven hardware or a service, whose
output is a finding rather than a feature. Use the protocol below.

If it is genuinely both — a spike whose success produces shippable code — run
the spike first, then propose the capability with the spike's findings in hand.
Do not write a spec against a service you have not yet reached.

---

## Spike protocol

A spike answers one question inside a fixed budget. **A spike that fails on time
is a success.** A spike that succeeds two days late has cost more than it
returned.

### Before starting — state these, and get agreement if they differ from the plan

1. **The question**, as something with a yes or no answer. "Does vLLM serve
   Lightning NVFP4 on the Spark at usable concurrency" is a question. "Set up
   vLLM" is not.
2. **The timebox**, in hours, from `docs/WEEK_ONE.md`.
3. **The pass gate** — the observation that ends the spike successfully.
4. **The abort ladder** — the ordered fallbacks and the point at which you stop
   and escalate rather than continuing.

### While running

- **Work on the real target.** A spike verified only on this laptop has answered
  a different question. Reach the Spark over LAN SSH with key auth; Tailscale
  SSH check-mode blocks scripted access.
- **Record every failure as you hit it**, typed, in the ledger — `dependency_build`,
  `oom`, `network`. This is the ledger's whole purpose, and the eight-week
  narrative of what broke is worth more than any individual fix.
- **Announce the timebox at the halfway mark** with an honest read on whether
  the gate is reachable. Half a budget spent with no path is the signal to drop
  to the next rung, not to push harder.
- **Never silently extend.** If the box is spent, say so, report where it got to,
  and take the next rung or escalate. Extending a timebox is the user's call.

### On finishing — pass or fail

- Record the outcome in `docs/WEEK_ONE.md` under that day: what happened, what it
  cost, what it changes for later days.
- Log the resolution against any failure signature that is now understood, so the
  ledger carries the fix and not just the wound.
- If the finding changes a plan or an interface, say which and update it. A spike
  whose findings do not reach the plan was not worth running.
- If it produced code, that code needs a capability and a spec. Do not let spike
  code become production code by default — it was written to answer a question,
  not to be maintained.
- Commit: the doc updates, and any throwaway harness under `scripts/spikes/`.
  Push.

### Cleaning up

Remove what you created on shared hardware and say what you removed. A spike
that leaves a venv, a container and a half-configured service behind has made
the next spike harder to trust.

---

## 4. Close out

At the end of a session, whether or not the item finished:

- State plainly what is done, what is not, and what the next session picks up.
- Update `docs/WEEK_ONE.md` if any day's reality diverged from its plan.
- Make sure nothing is left uncommitted, and nothing committed is unpushed.
- Name anything now blocked on a decision, with the decision stated clearly
  enough to answer without re-reading this conversation.

---

## Standing rules

- Verify on the Spark before believing anything about the Spark. Two defects
  have already passed locally and failed there.
- `COPYFILE_DISABLE=1` on transfers; macOS AppleDouble sidecars break migration
  discovery and the source scan.
- **Never `uv run` on the Spark.** It re-resolves the environment to x86_64 and
  destroys it.
- Model ids are the exact Token Factory console strings. Every id guessed from a
  marketing name has been wrong.
- A missing rate, an unreachable endpoint, an unclassifiable failure — let it be
  loud. Silence in a scored measurement is the failure mode this project is
  built to avoid.
- Push to `mgraves-centrix` only. **Never push to `master` or `main` on any
  `ditinc` remote.**
