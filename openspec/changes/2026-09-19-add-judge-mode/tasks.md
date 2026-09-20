# Tasks — `judge-mode`

Seven groups. Each leaves the gate green and is committed on its own.

## 1. Stop two changes claiming one requirement

- [x] 1.1 Removed from `2026-09-02-add-nebius-executor`'s delta, with the why
      recorded in that change's proposal. Six remote-dispatch requirements stay.
- [x] 1.2 Added verbatim here, with the requirements it needs beside it.
- [x] 1.3 **A `REMOVED` delta was the wrong instrument and is gone.** It named
      `nebius-executor` as a canonical spec — but that change has never archived,
      so no such spec exists and `REMOVED` would have tried to take a requirement
      out of nothing. `openspec validate --strict` passed it; archive would not
      have. Editing the parked change's own delta is the fix.

## 2. A night records what happened

- [x] 2.1 Stage start and end events, lane `system`, inside the stage's own
      transaction so a crashed night keeps what committed.
- [x] 2.2 Invocation events on the agent's role lane, with the turn's span.
- [x] 2.3 A failed stage writes an event with a severity; a skipped stage writes
      a note. Neither may collapse into the other.
- [x] 2.4 Test: a night through `run_entry` returns a non-empty timeline with
      more than one lane. **Mutation: remove the stage events and watch it go
      red** — today it would pass, because today there is no such test.
- [x] 2.5 Assert the lane is the work's lane, never the producer's role.
- [x] 2.6 **Found by rendering it: a skipped stage drew as a failure.** The
      scrubber collapsed `warn` and `error` into one color and the legend called
      both "a failure". Nothing had shown it — the seed writes only `info` and
      `error`, so no `warn` had ever reached the screen, and the morning already
      draws skipped amber and failed red. The two views contradicted each other
      about the same stage.
- [x] 2.7 And found by reading the render again: the new legend swatch had no
      `display: inline-block`, so it was a label with no color beside it. A test
      over the stylesheet's text passed throughout.

## 3. Artifacts can be read back

- [x] 3.1 A route addressed by artifact id. No path in the URL.
- [x] 3.2 A row naming a missing file is a 404, never an empty 200.
- [x] 3.3 Content type from the recorded kind, never sniffed.
- [x] 3.4 The morning's artifact list links to it.
- [x] 3.5 Test the refusals, including that no request can reach outside the
      artifact root, and that `model_call_payloads` is unreachable from here.
- [x] 3.6 The briefing had to carry artifact **ids** as well as paths. It sent
      paths alone, which was fine while nothing served artifacts and useless the
      moment something did.
- [x] 3.7 **The payload test was overbroad and is rewritten.** It grepped the
      route's source for "payload" — which the comment explaining the exclusion
      contains, so it forbade documenting the rule it checked. Asserted
      behaviorally now: the response is byte-identical to the file, and no
      registered route path mentions a payload.

## 4. The seed has an interview and real bytes

- [x] 4.1 Seeded decisions with rationales, deterministic by seed, at least one
      on a `local-only` entry so the egress warning has something to mark.
- [x] 4.2 Seeded artifacts get bytes whose hash matches the recorded one.
- [x] 4.3 Test: the same seed produces the same questions in the same order.
- [x] 4.4 Seeded artifact paths now follow the real `night_of/run_id/` convention
      instead of an invented `artifacts/<night>/` one, so a judge sees the path
      shape the product actually produces.
- [x] 4.5 **Tests were writing outside tmp.** `artifact_root()` falls back to
      `~/second-shift-data/artifacts`, harmless while nothing in-process wrote
      files and not harmless the moment the generator did. An autouse fixture in
      `conftest.py` now points it at each test's tmp directory.
- [x] 4.6 `NIGHT_TABLES` gained `decisions` — the existing audit caught the new
      table itself, which is what it is for.

## 5. The first screen says what this is

- [x] 5.1 An explanation block, rendered from the served capability report on
      `cloud`, absent otherwise. No build flag, no new endpoint.
- [x] 5.2 **Below the capture control.** `frontend` measured what chrome above
      the input costs: `local-only` from 79% visible to 0% at 390×350.
- [x] 5.3 Measured on both deployments at 390x350, the keyboard-up viewport
      `frontend` used: `local-only` is **100% visible on each**, explainer
      present on `cloud` and absent on `spark`. The explanation costs the
      privacy choice nothing.
- [x] 5.4 **Found by reading the render: the copy said "the night below" and
      there is no night below.** The night is its own surface. It points at the
      nav now.
- [x] 5.5 `profile.test.ts` failed because the new doc comment names
      `NEXT_PUBLIC_DEMO` to explain why it is forbidden — the same shape as the
      `process.env` over-reach that test already warns about. It strips comments
      before matching now, so the rule is about code and the clearest place to
      document it stays available.

## 6. The container

- [x] 6.1 `deploy/judge/Dockerfile`: a node stage builds the export, a
      `python:3.12-slim` stage installs `apps/api` and `packages/seed` against
      the same `constraints.txt` the Spark uses, then seeds the night and serves
      it. Every `COPY` names exactly what it takes — an allowlist stays correct
      when somebody adds a directory, and a denylist silently stops being one.
- [x] 6.2 `SECOND_SHIFT_SYNTHETIC=1`, `SECOND_SHIFT_PROFILE=cloud`. The profile
      is pinned rather than probed: a no-GPU VM resolves to `cloud` anyway, but
      a demo whose capability report depends on a probe behaving as expected in
      an environment nobody tested is a demo with a variable in it.
- [x] 6.3 Enforced three ways: the `COPY` allowlist, `.dockerignore` as a
      second line, and `check-judge-package.py` run at build against the
      database that was just seeded — which passes trivially today, and is there
      for the day somebody changes the line above it.
- [ ] 6.4 **Still open, and deliberately.** Build it and run it. The docker
      daemon is not reachable in this environment, and a deploy target verified
      only on paper is not verified — so this stays unchecked rather than
      claimed.

      What *was* verified, short of a build: every `COPY` source exists and none
      is excluded by `.dockerignore`; the seed and package-check steps were run
      with the image's exact environment; the `CMD` was run and served; and the
      `HEALTHCHECK` command exits 0 against it, reporting profile `cloud` with
      `local-only` unavailable for the pinned reason. Ten tests guard the file's
      shape, six mutations each killing one.

## 7. Synthetic containment, enforced

- [x] 7.1 Migration `0003_eval_synthetic`: `is_synthetic` on all three eval
      tables; the runner sets it from the deployment via `synthetic_flag()`,
      never from an argument a caller picks; `recorded_runs` and
      `awaiting_scoring` — the two reads a week-over-week comparison walks —
      exclude it. There are no views over these tables; the curve is read by
      the runner.
- [x] 7.1b **A migration test had to change to survive being one.** It asserted
      that a database at version 1 catches up by applying exactly `[2]`, so
      adding a third migration broke a test that was never about the third
      migration. It derives the expected list from what is on disk now.
- [x] 7.2 `scripts/check-judge-package.py` refuses a database carrying
      `model_call_payloads` rows or any unmarked row, with four tests — three of
      which exist only to prove it refuses. Not wired into the Spark deploy: that
      ships code only, no database and no brain. It is the container that bakes
      a database in, so group 6 calls it.
- [x] 7.2b **`model_call_payloads` stores paths, not text.** `prompt_path` and
      `completion_path` point at files under `data/payloads/`, which is where
      the content actually is — the schema's own PRIVACY comment reads as
      though the table holds it, and my first draft of this check repeated
      that. The rows are still worth refusing: they are an index of what the
      subject thought about and when. The image must additionally not copy
      those files, which is group 6's to enumerate.
- [x] 7.3 README recipe now sets `SECOND_SHIFT_SYNTHETIC=1`, with a line saying
      why it is not optional: seeded rows carry the flag already, but anything
      *captured* against an instance stood up without it is written
      `is_synthetic = 0`.

## 8. Verify and close

- [ ] 8.1 Full gate. Every new test shown able to fail, with the mutation named.
- [ ] 8.2 Stand up the container, open all three surfaces, **read the
      screenshots**, and report what a stranger said the product was — their
      words.
- [ ] 8.3 On the Spark: a real night, and confirm its timeline renders. This is
      the only way group 2 is actually proven, and it needs the machine.
- [ ] 8.4 Sync, archive, roadmap, and record anything deferred in the next
      capability's entry rather than only here.
