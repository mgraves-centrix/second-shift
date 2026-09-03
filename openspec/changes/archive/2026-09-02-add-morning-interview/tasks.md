# Tasks — `morning-interview`

## 1. The briefing

- [x] 1.1 `secondshift/morning/briefing.py`: assemble facts from `runs`,
      `run_stages`, `artifacts` and `failures`. Deterministic, no model call.
- [x] 1.2 The delta boundary as `MAX(decisions.answered_at_ms)`, derived.
- [x] 1.3 Stages reported with their status *and* reason, so skipped and failed
      are distinguishable.
- [x] 1.4 The three morning scenarios from the proposal, each asserted.

## 2. The interviewer

- [x] 2.1 Run the `interviewer` role against the assembled facts — **not** the
      raw entry text.
- [x] 2.2 Parse its questions and write `decisions`, each with a rationale and
      `raised_by_invocation_id`.
- [x] 2.3 A question with no rationale is refused rather than stored — a
      question without one is a quiz.
- [x] 2.4 An interviewer failure leaves the briefing's facts intact and returns
      no questions. Principle 3.

## 3. Answering

- [x] 3.1 Answer against a decision id through the existing `answer_decision`.
      No new free-text path.
- [x] 3.2 `text` modality recorded honestly; `voice` reserved for when ASR lands.
- [x] 3.3 `queued-for-tonight` answers readable as pending input, and
      `consumed_by_run_id` written when a run takes one.
- [x] 3.4 Defer and obsolete are retained states, never deletions.

## 4. The policy upgrade

- [x] 4.1 A widening answer passes `upgrade_decision_id` to `resolve_policy`.
- [x] 4.2 Widening with no decision is refused — assert the negative.
- [x] 4.3 The warning travels on the question as data, not in a component.

## 5. Verification

- [x] 5.1 The three mornings render what the proposal says they do.
- [x] 5.2 A partial night shows its completed stages.
- [x] 5.3 Rendering does not advance the boundary; answering does.
- [x] 5.4 **No hardcoded questions.** Assert the module contains no question
      string — every question comes from a `decisions` row.
- [x] 5.5 **No free-text instruction path.** Assert the answer surface takes a
      decision id.
- [x] 5.6 Full suite, both guards, `openspec validate --strict`.

## 6. Not built, recorded rather than dropped

- [x] 6.1 **The screen.** `FRONTEND.md` must land first — its own prompt says so,
      and `/` and `/night/` still have no navigation between them while design
      tokens drift across two files. The server half is reachable through the
      API; the rendered interview is `FRONTEND.md`'s to unblock.
- [x] 6.2 **Whether it feels like an interview.** The prompt's most useful report
      item, and it needs the screen and a real phone. Unanswered, not answered
      badly.
- [x] 6.3 **Voice, entirely.** No ASR exists; an input visualization with no
      transcription behind it is the decoration the prompt names.
- [x] 6.4 **Acknowledging a question-free night.** The delta rule's accepted
      trade: such a night reappears until something is answered. Fixing it needs
      a column or table that does not exist.


## Mutations run

| Mutation | Result |
|---|---|
| **Rule B** — the briefing takes only the most recent run | 3 red, including `test_two_nights_with_no_interview_both_appear` |
| Deferring stops counting as acting | `test_deferring_counts_as_acting` red |
| A question with no `Why:` is stored anyway | `test_a_question_without_a_rationale_is_discarded` red |
| The interviewer is handed the raw entry text | `test_the_interviewer_is_not_handed_the_raw_entry_text` red |

The first is the open decision's mutation: implementing the rule that was
rejected on paper turns the mornings red in the data, which is what makes the
argument in the proposal checkable rather than merely written down.

## Two defects in this change's own tests, caught before commit

- **A "no hardcoded questions" test that was matching SQL placeholders.** It
  grepped the source for `?"` and the module's `WHERE ... IN (?)` clauses
  satisfied it, so it would have passed forever whatever the module did.
  Replaced with the behavior it was meant to protect: an empty database produces
  zero questions, one row produces exactly that row's question.
- **A failure fixture with no run attached.** `record_failure` reads the run
  from the invocation context and there was none, so the reason lookup found
  nothing and the test failed for the wrong reason. Rewritten to insert against
  the run explicitly.

## The gap this change found and did not close

**`run_stages` has no reason column.** `night-pipeline` returns a skip reason in
`StageResult.reason` and never persists it, so:

- A **failed** stage's reason is recoverable — the night records failures scoped
  `night.<stage>` and `signature()` embeds that scope, so `_failure_reasons`
  reads it back without a schema change.
- A **skipped** stage's reason is not stored anywhere. The briefing reports
  *that* it was skipped and not *why*.

Rather than a `reason` field that is always `None` — a plausible constant, which
the quality bar names — the briefing carries the reason only where one exists and
the module says so. The common skips (`local-only`, no credential) are derivable
from the run's policy and the deployment's configuration, so nothing is
unknowable; it is just not one query. **Closing it properly is a migration**,
which is a data-model change beyond this capability.

## The three mornings, rendered

```
Morning 1 — after a clean night
    nights: 1   2026-09-02 degraded: completed [brief, mockups, distill]

Morning 1 again — rendered, nothing answered
    nights: 1   ← rendering did not consume it

Morning 3 — two nights, no interview between
    nights: 2   ← neither night lost

After answering
    nights: 1   ← the boundary advanced
```


## Corrected after archiving, by an audit of this change's own claims

**The proposal says the server half is "reachable through the API". It was not.**
The morning package had no caller anywhere in the tree — no route, no CLI,
nothing. It imported and tested cleanly and no running system could reach it.
The claim is left as written above because it is the record of what was believed;
what fixed it is here.

- `GET /morning` and `POST /decisions/{id}/answer` now exist.
  `API_LAYER.md`'s scope says "no new routes; a capability adds its own", so they
  were always this capability's to add and their absence was an oversight rather
  than a boundary.
- **`include_synthetic` had no caller and no test**, despite being principle 5's
  hook: the judge deployment runs this same code over seeded rows, and a
  briefing that filtered them would show a judge an empty morning. It is now set
  from the deployment's own flag — never from a request — and both directions
  are asserted.
- **Two dead properties removed**: `StageLine.ran` and `NightLine.produced`,
  defined and called by nothing.
- **One test strengthened after a mutation exposed it.** The
  rendering-does-not-consume test had no open decision in it, so a mutation that
  consumed decisions on render could not reach it. A test that cannot reach the
  mechanism it names is testing the absence of data.

Three route mutations were run and each turned its test red: a `GET` that
consumes its own delta, the judge flag read from the query string instead of the
deployment, and an unknown decision id accepted rather than refused.
