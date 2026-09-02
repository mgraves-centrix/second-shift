# Tasks — `morning-interview`

## 1. The briefing

- [ ] 1.1 `secondshift/morning/briefing.py`: assemble facts from `runs`,
      `run_stages`, `artifacts` and `failures`. Deterministic, no model call.
- [ ] 1.2 The delta boundary as `MAX(decisions.answered_at_ms)`, derived.
- [ ] 1.3 Stages reported with their status *and* reason, so skipped and failed
      are distinguishable.
- [ ] 1.4 The three morning scenarios from the proposal, each asserted.

## 2. The interviewer

- [ ] 2.1 Run the `interviewer` role against the assembled facts — **not** the
      raw entry text.
- [ ] 2.2 Parse its questions and write `decisions`, each with a rationale and
      `raised_by_invocation_id`.
- [ ] 2.3 A question with no rationale is refused rather than stored — a
      question without one is a quiz.
- [ ] 2.4 An interviewer failure leaves the briefing's facts intact and returns
      no questions. Principle 3.

## 3. Answering

- [ ] 3.1 Answer against a decision id through the existing `answer_decision`.
      No new free-text path.
- [ ] 3.2 `text` modality recorded honestly; `voice` reserved for when ASR lands.
- [ ] 3.3 `queued-for-tonight` answers readable as pending input, and
      `consumed_by_run_id` written when a run takes one.
- [ ] 3.4 Defer and obsolete are retained states, never deletions.

## 4. The policy upgrade

- [ ] 4.1 A widening answer passes `upgrade_decision_id` to `resolve_policy`.
- [ ] 4.2 Widening with no decision is refused — assert the negative.
- [ ] 4.3 The warning travels on the question as data, not in a component.

## 5. Verification

- [ ] 5.1 The three mornings render what the proposal says they do.
- [ ] 5.2 A partial night shows its completed stages.
- [ ] 5.3 Rendering does not advance the boundary; answering does.
- [ ] 5.4 **No hardcoded questions.** Assert the module contains no question
      string — every question comes from a `decisions` row.
- [ ] 5.5 **No free-text instruction path.** Assert the answer surface takes a
      decision id.
- [ ] 5.6 Full suite, both guards, `openspec validate --strict`.

## 6. Not built, recorded rather than dropped

- [ ] 6.1 **The screen.** `FRONTEND.md` must land first — its own prompt says so,
      and `/` and `/night/` still have no navigation between them while design
      tokens drift across two files. The server half is reachable through the
      API; the rendered interview is `FRONTEND.md`'s to unblock.
- [ ] 6.2 **Whether it feels like an interview.** The prompt's most useful report
      item, and it needs the screen and a real phone. Unanswered, not answered
      badly.
- [ ] 6.3 **Voice, entirely.** No ASR exists; an input visualization with no
      transcription behind it is the decoration the prompt names.
- [ ] 6.4 **Acknowledging a question-free night.** The delta rule's accepted
      trade: such a night reappears until something is answered. Fixing it needs
      a column or table that does not exist.
