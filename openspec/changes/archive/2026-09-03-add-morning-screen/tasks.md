# Tasks — `app/morning/`

## 1. The server-side gap this screen would otherwise render a lie about

- [x] 1.1 `will_leave_the_machine` set from the entry's `default_policy`.
      `_open_questions` currently constructs every question without it, so the
      field has never once been `true` and a shipped spec says it is.
- [x] 1.2 A test that **must be able to fail**: mark a question on a
      `cloud-assisted` entry and the test should go red. Assert the value, not
      the key's presence — the existing test asserts presence, which is why the
      suite was green with the feature missing.

## 2. `lib/morning.ts`

- [x] 2.1 Response types mirroring `BriefingResponse` exactly. No `any`.
- [x] 2.2 `submitAnswer(decisionId, ...)` — one function, and the decision id is
      a required positional. A signature that could be called without one is the
      chat interface with extra steps.
- [x] 2.3 `stageReason(stage)` — the three-state rule, including "no reason
      recorded" for a skipped stage.
- [x] 2.4 `LEAVES_THE_MACHINE` — the warning copy, once, beside the rule.

## 3. The screen

- [x] 3.1 `app/morning/page.tsx` on the `Nav` shell. Questions first, the
      night's record below.
- [x] 3.2 One question at a time, with the agenda's length visible.
- [x] 3.3 Four outcome controls, all advancing.
- [x] 3.4 The leaves-the-machine warning on the marked questions.
- [x] 3.5 The partial-night record: complete, failed with reason, skipped.
- [x] 3.6 `interviewer_error` above the record, never instead of it.
- [x] 3.7 A failed submission says the answer was not recorded and keeps the text.
- [x] 3.8 `useEffect` with an `AbortController`, matching night's idiom.
- [x] 3.9 `app/morning/morning.module.css` — no color of its own.

## 4. Registration

- [x] 4.1 `/morning/` in `SURFACES`. One line; both shells pick it up.
- [x] 4.2 A test that every registered surface has a route on disk — the
      extension point is only safe if a typo in it fails a test rather than a
      click.

## 5. Verification

- [x] 5.1 Principle 4: assert the surface references no `getUserMedia`,
      `MediaRecorder` or `SpeechRecognition`. Mutation: add one, see it fail.
- [x] 5.2 Principle 6: assert every submission carries a decision id.
- [x] 5.3 The three stage states render distinguishably.
- [x] 5.4 The empty morning is a sentence, not an error.
- [x] 5.5 Every new test shown able to fail. Record which mutation was used.
- [x] 5.6 `npm run typecheck`, `npm run build`, both guards, `openspec --strict`.

## 6. The interview I have to actually do

- [x] 6.1 Seed a database with a partial night and real raised questions —
      through the night pipeline and the interviewer, not by inserting rows.
- [x] 6.2 Serve the built export from the API and drive it in Chromium.
- [x] 6.3 Screenshot at 390 and 1280. **Open the images and read them.**
- [x] 6.4 Answer a question end to end and verify the row changed.
- [x] 6.5 Report whether it felt like an interview or a form. Honestly.

## 6b. What the render turned up that no test would have

Four defects, every one found by looking at the built page rather than by a
suite that was green throughout.

- [x] 6b.1 **The night's record was three times taller than the interview.**
      Every artifact rendered its full path, so the run's 26-character ULID
      appeared six times and the reader had to hunt for the differing tail.
      Fixed with `artifactLabel`, which strips the prefix already on screen and
      returns an unrecognized path whole rather than trimming on a guess.
- [x] 6b.2 **`Decided` carried the accent**, which reads as the recommended
      answer — and a person in a hurry clicks the highlighted button, which
      biases the record away from `Defer`. Deferring being first-class has to
      be true of the pixels or it is only true of the schema. All four are
      equal now.
- [x] 6b.3 **The empty morning claimed the night got stuck on nothing** — on a
      morning with no night at all. That is the state you land in *immediately
      after an interview*, because acting advances the delta boundary past the
      run you just discussed. Found by reloading the page after answering.
- [x] 6b.4 **The interviewer's question order was lost to a ULID tiebreak.** A
      whole turn's questions are written in the same millisecond, so
      `ORDER BY raised_at_ms, id` sorted them by random bits — observed
      reversing them between two runs of the same seed. On a list that is
      untidy; on a screen that asks one question at a time it spends the
      interviewer's judgment about which matters most. Fixed with
      `ordered_ulids`, additive and used only where ordering is known.

The first version of 6b.3's test read the branch out of `page.tsx` and matched
the explanatory comment above the code rather than the code. That is exactly
the failure `lib/morning.ts` exists to prevent, so the copy moved into the
module and the test asserts behavior.

## 7. Close out

- [x] 7.1 Sync specs, archive, drift pass over prompt/roadmap/index.
- [x] 7.2 Follow-up audit: the orphan check over every new public symbol.

## 8. The follow-up audit — two orphans

The orphan check, run over every public symbol in `lib/morning.ts`: *does
anything outside this module reference it?*

- [x] 8.1 **`AnswerResult` was exported and imported by nothing.** The same
      finding the shell's `DemoLabel` produced. Un-exported; a caller that
      wants the recorded status gets it by inference from `submitAnswer`.
- [x] 8.2 **`completedStages` had a test and no production caller.** Correct,
      tested, unreachable — the defect this project keeps producing. It was
      genuinely wanted, so the fix was a caller rather than a deletion:
      `nightSummary` renders "5 of 6 complete" beside the date, which is the
      "short enough to read standing up" the brief asks for and which six rows
      of status is not.

`StageLine`, `NO_REASON_RECORDED` and `completedStages` are still referenced
only by tests, and each legitimately: `StageLine` is structural inside
`NightLine`, `NO_REASON_RECORDED` is named by its test rather than duplicated
as a string literal, and `completedStages` now has `nightSummary`.
