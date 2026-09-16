# Design — `app/morning/`

## The shape of the screen

```
  ┌─ Nav ──────────────────────────────────────────────── demo? ─┐
  │                                                              │
  │  2 of 4                                    [ ● ○ ○ ○ ]       │
  │                                                              │
  │  Should the research stage keep going without a source        │
  │  for the second claim?                                        │
  │                                                              │
  │  Why: the brief asserts it, the digest found nothing that     │
  │  supports it, and continuing would build on an unsourced      │
  │  premise.                                                     │
  │                                                              │
  │  ┌────────────────────────────────────────────────────────┐  │
  │  │ your answer                                            │  │
  │  └────────────────────────────────────────────────────────┘  │
  │                                                              │
  │  [ Decided ] [ Queue for tonight ] [ Defer ] [ Obsolete ]     │
  │                                                              │
  ├─ Last night ─────────────────────────────────────────────────┤
  │  2026-09-02 · cloud-assisted                                 │
  │    brief      complete   1 artifact                          │
  │    research   failed     no API key configured               │
  │    mockups    skipped    no reason recorded                  │
  └──────────────────────────────────────────────────────────────┘
```

## One question at a time

The state is an index into `questions` and nothing else. There is no way to
reach question 3 without disposing of question 2, and every one of the four
outcomes advances the index — including *Defer*, which is the point: deferring
being a first-class outcome in the schema is only meaningful if the screen
treats it as one, rather than as the thing you do by scrolling past.

The agenda is visible as a dot per question, so the interview has a length. An
interview whose end you cannot see is a queue.

**Why this and not a list.** A list of questions with a box under each is a
form, and a form is answered easy-first. The night's blocker is rarely the easy
one. This is also the anti-chat argument in layout: with one agenda item on
screen, whose text box is rendered *inside* a specific question, there is no
place to put an instruction that is not an answer to something asked.

## Why logic lives in `lib/morning.ts`

`node --test` strips TypeScript types but does **not** transform JSX, so
anything in a `.tsx` can only be asserted by reading the file's text — and a
test that greps source passes when the symbol it names has been renamed. This
was learned the hard way in `frontend`, where the surface list had to be moved
out of `Shell.tsx` for exactly this reason.

So the module holds the response types, the answer client, the stage-line
formatting, and the warning copy. The page holds layout and `useState`.

## `will_leave_the_machine`, and what the rule can honestly be

**The rule: a question is marked when the entry it was raised against has
`default_policy = 'local-only'`.**

Derived from rows, no new column. It is the exact set for which the flag can
mean anything: `resolve_policy` widens only `local-only`, so on a
`cloud-assisted` entry there is nothing to widen and the idea has already left.

**It over-warns, deliberately.** Answering *Defer* or *Obsolete* on a marked
question sends nothing anywhere. The alternative — marking only the specific
answer that authorizes — is not derivable, because `decisions` has no column
that distinguishes "yes, take it to the cloud" from any other queued answer.
Between warning about an answer that turns out to be harmless and not warning
about one that is not, principle 2 picks the first.

**The copy carries the precision the flag name cannot.** `will_leave_the_machine`
overstates: it reads as *this will happen*, and what is true is *an answer here
is the only thing that could authorize it*. Renaming a field in a shipped spec
and a shipped API to fix a sentence is the wrong trade, so instead the warning
text is a single exported constant in `lib/morning.ts`, sitting next to the rule
it describes. No component writes its own wording from the field's name — which
is the same failure mode the demo label had, where a prop every caller had to
remember went missing on the one screen a judge opens first.

## Unreachable API: reading and writing are not the same notice

The night surface says *"Nothing was lost — this view only reads."* That
sentence is true there and false here. This screen writes: a failed
`POST /decisions/{id}/answer` means the answer was **not** recorded, and the
screen says so and keeps the text in the box. Reusing the night's reassurance
would be telling someone their answer is safe at the moment it is lost.

## Partial nights, and the three states a stage can be in

Principle 3 is a rendering rule here, not an assembly one — assembly already
returns partial results. The screen must not collapse them:

| status | shown as | reason |
|---|---|---|
| `complete` | the stage, with its artifact paths | — |
| `failed` | the stage, with the message from the ledger | recovered by signature |
| `skipped` | the stage, with **"no reason recorded"** | `run_stages` has no reason column |

"No reason recorded" rather than a blank, because a blank reads as *no reason*
and the truth is *not stored*. That gap is carried forward from
`morning-interview` and closing it is a migration.

`interviewer_error` renders as a line above the night's record — the facts, and
why there are no questions beside them. Never instead of the facts.

## The empty morning

No questions and no nights is a legitimate state: nothing has run since the last
answer. It renders as "Nothing has run since your last answer" — which is a
report, not an error, and not an empty page. Principle 3's violation is *an
error instead of partial results*; a truthful sentence about zero results is
neither.

## Voice

Not built. The screen references no microphone API, and the test asserts that by
name (`getUserMedia`, `MediaRecorder`, `SpeechRecognition`), which is a stronger
statement of principle 4 than mocking a denial: code that never asks cannot be
refused. `answer_modality` is sent as `text` explicitly rather than by default,
so the column that will carry `voice` has a caller passing it today.
