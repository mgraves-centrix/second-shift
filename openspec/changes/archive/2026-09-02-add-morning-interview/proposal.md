# Add `morning-interview` — the briefing, the questions, and the answers

## Scale classification

**L3 — Epic.** It writes the `decisions` state machine that has sat unused since
the first migration, it is the only path that widens a policy, and it is where
principle 1's learning claim becomes an actual write. Design doc included.

## Why

**The interview is the product.** The pitch is "it interviews you in the morning
about what it got stuck on," and everything shipped so far captures, stores,
reasons or renders. A submission without this is a well-instrumented batch job.

Verified against the tree rather than quoted:

- `decisions` has **one caller in the entire repository**, and it is a test
  (`test_persistence.py:116`). Not the night, not the seed, not any agent path.
- `resolve_policy(..., upgrade_decision_id=)` exists and records
  `policy_source = 'decision-upgrade'`, and **nothing has ever passed it**.
- `decisions.consumed_by_run_id` and the `queued-for-tonight` status exist with
  nothing writing either.

## What this change does not build, and why

**`FRONTEND.md` has not shipped, and its own prompt says it "must land before
`MORNING_INTERVIEW.md`."** The reason is concrete and checkable: `/` and
`/night/` have no navigation between them, and design tokens are already
drifting across `app/globals.css` and
`components/scrubber/scrubber.module.css`. Adding a third surface on that
foundation makes the drift worse — which is precisely what `FRONTEND.md` exists
to stop.

So **the server half ships and the screen does not**: briefing assembly, the
interviewer raising decisions, answering with a modality, and the policy
upgrade — reachable through the API and exercised by tests. The screen is
`FRONTEND.md`'s to unblock.

**The consequence, stated plainly:** the prompt's report asks whether the
interview *felt* like being interviewed or like filling in a form. That question
is unanswerable here and is not answered. It is the most useful question in the
prompt and it stays open.

## The open decision — what the briefing is a delta of

Worked against the three mornings the prompt names, with the candidate rules.

**Rule A — since the last *interview*** (the most recent answered decision).
**Rule B — since the last *night***.
**Rule C — since you last *opened* it**.

### Morning 1 — after a clean night

> **Last night.** One idea worked: *a weekly digest of voice notes*. Five of six
> stages completed; research was skipped because no search credential is
> configured. It produced a brief, a mockup, a build and a critique.
>
> **One question.** The builder had two defensible shapes for the digest and
> could not choose without knowing whether you read it on a phone. It would pick
> the phone-first one. Overrule it?

All three rules agree. This morning does not discriminate.

### Morning 2 — after a night you never read

> **Last night, and the night before, which you have not seen.** Two ideas...

- **Rule A:** correct. You have answered nothing, so nothing is consumed, and
  both nights appear.
- **Rule B:** **wrong.** Only the most recent night shows, and the unread one is
  silently gone — work the system did that you will never be told about.
- **Rule C:** **wrong in the worst way.** You *opened* it and did not act, so the
  boundary advanced and the questions vanish. Opening a briefing on a phone while
  walking is not the same as deciding anything.

### Morning 3 — two nights, no interview between them

Same shape as morning 2, and the same verdict: **A correct, B loses a night, C
loses both if the app was ever opened.**

### The rule

**The briefing covers every run since the most recently *answered* decision.**
Rendering a briefing consumes nothing; only acting does. A decision that was
answered, deferred or marked obsolete counts as acted on — deferring is a
choice, and the prompt names it as a first-class outcome.

**Where the boundary lives:** `MAX(decisions.answered_at_ms)`. Derived, no new
table, matching `docs/DATA_MODEL.md`'s convention that counters are views.

**The trade this rule accepts, named rather than hidden:** a night that raised
*no* questions can never be consumed, so it reappears the next morning. That is
mildly repetitive and it is the safe direction — it never hides work from you,
and principle 3's concern is empty mornings, not repeated ones. An explicit
"I have read this" acknowledgement would fix it and needs a table or a column
that does not exist; **recorded as a follow-up, not built.**

## The second open decision — voice

**The input half is deferred entirely. Nothing microphone-shaped ships.**

There is no ASR. Building an input visualization against a microphone with no
transcription behind it produces exactly what the prompt calls decoration — "a
bouncing waveform, and every demo has one." It would also invite a turn that
only speaking can complete, which principle 4 calls a violation rather than a
limitation.

`answer_modality` already has a `voice` value in its CHECK, so the recording
path is ready when ASR lands. What ships records `text`, honestly, because that
is what happened.

## Constitution compliance

| Principle | Outcome | Why |
|---|---|---|
| 1. Brain plaintext under git | **Constrains** | What the interview learns is the brain's to hold. This change writes `decisions`; the brain write is `distill`'s, already shipped, and the topic-file diff remains the learning claim. |
| 2. Privacy Airlock | **Constrains** | A policy upgrade happens *only* through `upgrade_decision_id`, so widening is always attributable to an answer a person gave. The briefing states that the idea will leave the machine before the answer is recorded, not after. |
| 3. No empty mornings | **Governs** | The briefing is built from whatever stages reached `complete`, so a partial night presents its parts. It renders no error in place of partial results — and by the delta rule above it never silently drops a night either. |
| 4. Text-first | **Governs, and decides the voice question** | Every turn completes by typing because typing is the only path that exists. Voice is deferred rather than half-built. |
| 5. One codebase, two deployments | **Constrains** | No demo branch; the judge instance runs the same assembly over synthetic rows. |
| 6. Scope boundary | **Compliant, and this is the live risk** | Checked against both `NOT_BUILDING.md` tables. **"A general chat interface" is on the Excluded table by name**, and the prompt calls it the single most likely way this goes wrong. There is no free-text endpoint that accepts arbitrary instructions: an answer is submitted *against a specific decision id*, and a decision that does not exist is refused. Answered/deferred/obsolete are decision states, not a backlog — no status, assignee or due date. |
| 7. Telemetry from line one | **Constrains** | The interviewer runs as a recorded agent invocation, and each decision it raises names that invocation in `raised_by_invocation_id`. |

No violations.

## Non-goals

- No screen. See above.
- No ASR, no microphone, no speech visualization.
- No evening or at-capture interview (ADR 0005).
- No general chat interface, no free-text instruction endpoint, no task list.
- **No acknowledgement of a question-free night**, which the delta rule's trade
  would want. Recorded, not built.
