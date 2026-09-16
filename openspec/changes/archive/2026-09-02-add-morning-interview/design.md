# Design — `morning-interview`

## Context

`decisions` has carried the whole interview state machine since
`0001_initial.sql` — five statuses, a rationale, a modality, and
`consumed_by_run_id` — with exactly one caller in the repository, a test. The
schema also settles who writes it: `raised_by_invocation_id` is commented *which
interviewer version asked*, and the shipped `interviewer.v1.md` prompt agrees.

So the questions are produced at briefing time by an interviewer reading the
night's record. `night-pipeline` correctly does not write this table, and this
design does not change it.

## Decision 1 — the briefing is assembled from rows, and the interviewer reads it

Two steps, not one:

```
runs + run_stages + artifacts + failures ──> Briefing (facts)
                                    Briefing ──> interviewer ──> decisions
```

The facts are assembled deterministically. The interviewer is a model call that
turns them into questions. Splitting them matters for three reasons:

- **The briefing survives a model failure.** Principle 3: if the interviewer
  cannot run, the morning still shows what the night produced. A design where
  the model produces the whole briefing renders an error on exactly the morning
  it matters most.
- **The facts are testable without a model.** The three morning scenarios assert
  on the assembled briefing, not on generated prose.
- **The questions are attributable.** Each decision names the invocation that
  raised it, so a prompt change is visible in the record rather than inferred.

**Alternative considered:** have the interviewer read the database directly and
emit both narrative and questions. Rejected — it makes the morning depend on a
model call, and it puts prose between the person and the facts.

## Decision 2 — an answer is submitted against a decision id, never as free text

`answer_decision(decision_id, answer, status, answer_modality)` already exists.
The interview adds no endpoint that takes an instruction.

This is the scope boundary made structural. `NOT_BUILDING.md` excludes a general
chat interface by name, and the prompt calls it the single most likely way this
capability goes wrong. The guard is not a rule to remember: there is no path that
accepts arbitrary text and routes it somewhere. An answer is always *to a
question the system asked*, and an unknown decision id is refused.

**Alternative considered:** a `POST /interview/message` that classifies intent.
Rejected — that is the chat interface with a different name, and it would grow.

## Decision 3 — the delta boundary is derived, not stored

`MAX(decisions.answered_at_ms)` is the boundary. No `interviews` table, no
`last_seen_at` column.

**Alternative considered:** an `interviews` table recording each session.
Rejected on the same convention that keeps counters as views — the boundary is a
fact about `decisions` and storing it separately creates two things that can
disagree, with the stored one winning silently.

**The consequence is real and accepted:** a night that raised no questions has
nothing to answer, so the boundary does not advance and that night reappears.
Repetitive, and safe in the direction that matters. The alternative — advancing
the boundary on render — is Rule C from the proposal, which loses a briefing
because somebody glanced at their phone.

## Decision 4 — a policy upgrade is an answer, and the warning precedes it

An answer with `widen_policy=True` writes the decision and *then* the caller
passes `upgrade_decision_id` to `resolve_policy`. The decision row is what makes
the widening attributable, so it must exist first.

The briefing carries the warning text as data — `will_leave_the_machine` on the
question — rather than leaving it to a screen to remember to say. A warning that
lives only in a component is a warning the next component forgets.

**Alternative considered:** a `widen` flag on the run. Rejected outright — that
is the "configuration flag that disables the airlock" shape, and principle 2
names it.

## Decision 5 — the interviewer sees the night, not the entry

The interviewer is handed assembled facts: which stages completed, what they
produced, which failed and why. It is **not** handed the raw entry text.

It does not need it — its job is "what got stuck", which is a property of the
run — and not passing it means a `cloud-assisted` interview does not put the
original idea in front of a remote model a second time. Under `local-only`
nothing reaches a remote provider anyway, but the narrower input is correct on
both profiles and costs nothing.
