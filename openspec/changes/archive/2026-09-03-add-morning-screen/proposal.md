# Add `app/morning/` — the interview, one question at a time

## Scale classification

**L3 — Epic.** The interview is the product. Everything shipped so far is
scaffolding for this screen: the pitch is "it interviews you in the morning
about what it got stuck on," and until now the only thing that has ever
conducted an interview is a pytest. It also closes a false claim in a shipped
spec (below), which makes it a correction as well as an addition. Design doc
included.

## Why

`morning-interview` shipped its server half on 3 Sep — briefing assembly, the
interviewer raising decisions, answering with a modality — deliberately without
a screen, because `frontend` had not landed and there was no navigation or token
system to hang one on. `frontend` shipped later the same day and closed both.

So `GET /morning` and `POST /decisions/{id}/answer` exist, are tested, and have
never been used by a person. The report item the prompt asks for — *did it feel
like being interviewed?* — has been unanswerable, because there was nothing to
answer it about.

## What reading the server half turned up

Two fields that are correct, typed, serialized, and never set. This is the same
defect class the last four capabilities each produced one of, and it is worth
naming again: **a capability can be complete, tested and unreachable.**

### 1. `will_leave_the_machine` is always `false` — and a spec says otherwise

`morning-interview`'s spec carries this scenario:

> **Scenario: The person is told before the idea leaves**
> **WHEN** a question would widen a policy if answered
> **THEN** the briefing marks that question as one whose answer sends the idea
> off the machine

`briefing.Question.will_leave_the_machine` defaults to `False`. `_open_questions`
constructs every `Question` without it. Nothing anywhere assigns `True`. The one
test that names the field asserts the *key is present in the JSON*, not that it
is ever set — which is why a suite at 587 passing did not catch it.

**That scenario is false today.** It is fixed here rather than recorded, because
it is precisely the warning this screen is required to display, and building a
screen that renders a flag the server never raises would be building the
warning's appearance rather than the warning.

### 2. `blocking_stage` is always `NULL`

`Repository.insert_decision` accepts it; `raise_questions` never passes it. No
spec claims otherwise, so this is an unset field rather than a false claim —
recorded below, not fixed, because closing it means changing the interviewer's
output format, which is the server half's business and not the screen's.

## The open decision — what makes this an interview and not a form

The prompt asks, in the report, whether the interview *felt* like an interview
or like filling in a form. That is a question about one design decision, so it
is better decided than discovered.

**A list of four questions, each with a text box and four buttons, is a form.**
It is the shape every issue tracker has. It also invites answering the easy ones
and leaving the rest, which produces a morning where the thing that actually
blocked the night is still open.

**So: one question at a time, with the agenda visible.** "2 of 4" above it, the
rationale under it, four outcome buttons, and no way to see question 3 without
disposing of question 2. Every outcome advances — including *Defer*, which is
why deferring being first-class matters structurally and not just in the schema.
An interview you cannot skip ahead in is the difference.

This is also the anti-chat argument made in layout. `NOT_BUILDING.md` excludes a
general chat interface by name and the prompt calls it the live risk. A screen
with one agenda item on it at a time, whose text box is rendered inside a
specific question and whose submit path is `POST /decisions/{id}/answer`, has
nowhere to put an arbitrary instruction. The scope boundary is the URL, and the
layout agrees with it.

**What goes at the top.** The prompt says the briefing "says what happened, what
it produced, and what it could not decide" — night first, questions last. This
inverts it: **questions first, the night's record below.** The reason is that a
question already carries its context. `rationale` is specified as *"what you
tried, why it stopped, and what you need from them"*, so a question is
self-contained and a person with thirty seconds should spend them being
interviewed rather than reading a stage table. The night's record stays on the
same screen, under the agenda, for the answer that needs it.

## The second open thing — voice

**Deferred entirely, and stated rather than half-built.**

- There is no ASR. ADR 0006 binds Parakeet Realtime EOU and it **has never been
  run.** The 80–160ms end-of-utterance decision is what makes push-to-talk feel
  right, and nothing has measured it.
- A microphone visualization with no transcription behind it is decoration. The
  prompt says so in its own words: *"A bouncing waveform is decoration and every
  demo has one."* Putting one on the screen that is the product would be
  spending the most valuable surface in the submission on a control that does
  nothing.
- Principle 4 is satisfied by *not* building it, not despite it. The principle
  is that voice must never be on the critical path and text must never be a
  degraded fallback. Text being the only path is the strongest possible form of
  that, and `decisions.answer_modality` already accepts `voice`, so the column
  is waiting rather than the screen being rebuilt.

The principle-4 test this implies is stronger than a mocked permission denial:
**assert the morning surface references no microphone API at all.** Code that
never asks for a microphone cannot be affected by a person refusing one.

## What Changes

- `app/morning/` — the interview, on the `Nav` shell, registered in `SURFACES`
  so it appears in the nav and capture's footer at once.
- `lib/morning.ts` — the types, the answer client, and every piece of logic that
  can be wrong invisibly. In `.ts` rather than in the page, because the web
  suite runs under `node --test`, which strips types but does not transform
  JSX; logic in a `.tsx` can only be asserted by grepping the file's text.
- The `will_leave_the_machine` fix, in `morning/briefing.py`.

## What does not ship, and why

- **No ASR spike.** Its own session, as the prompt says.
- **No microphone visualization.** Above.
- **No free-text route.** There is no control on this screen that submits text
  without a decision id, and a test asserts it.
- **No editing artifacts in-app.** They are listed as paths and land as files.
- **No task list.** Four decision states, not a backlog.

## Recorded, not built

- **The night never passes `upgrade_decision_id`.** `resolve_policy` widens
  `local-only` to `cloud-assisted` with an attributable decision, and
  `quarantine.py` threads the parameter, but `run_entry` never supplies one — so
  no answer has ever actually widened a policy. Closing it is **not** a wiring
  change: `decisions` has no column distinguishing *"yes, take this one to the
  cloud"* from any other `queued-for-tonight` answer, and treating the presence
  of a queued answer as authorization would send a local-only idea off the
  machine on an answer that said the opposite. That is the Privacy Airlock
  failure the mechanism exists to prevent. **Recommendation:** a migration
  adding `authorizes_widening INTEGER NOT NULL DEFAULT 0` to `decisions`, set
  only by an explicit control on this screen, consumed by `_take_queued_answers`.
  A data-model change, and its own change.
- **`blocking_stage` is always `NULL`.** Above. **Recommendation:** extend
  `FORMAT_INSTRUCTION` with a third line and have `parse_questions` return it —
  safe for the eight-week curve, because `FORMAT_INSTRUCTION` deliberately lives
  outside the prompt file and does not enter `prompt_sha`.
- **`run_stages` has no reason column**, so a skipped stage reports *that* and
  not *why*. Carried forward from `morning-interview`; the screen says "no
  reason recorded" rather than leaving a blank, which is honest about which of
  the two it is.

## Impact

- `openspec/specs/morning-interview/` — one scenario becomes true; the screen's
  requirements are added.
- `openspec/specs/frontend/` — a third surface joins `SURFACES`.
- `apps/api/secondshift/morning/briefing.py` — `will_leave_the_machine` is set.
- `apps/web/app/morning/`, `apps/web/lib/morning.ts`, `apps/web/lib/surfaces.ts`.
- The capture PWA is not touched. It is taking real ideas.
