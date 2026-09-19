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

- [ ] 4.1 Seeded decisions with rationales, deterministic by seed, at least one
      on a `local-only` entry so the egress warning has something to mark.
- [ ] 4.2 Seeded artifacts get bytes whose hash matches the recorded one.
- [ ] 4.3 Test: the same seed produces the same questions in the same order.

## 5. The first screen says what this is

- [ ] 5.1 An explanation block, rendered from the served capability report on
      `cloud`, absent otherwise. No build flag, no new endpoint.
- [ ] 5.2 **Below the capture control.** `frontend` measured what chrome above
      the input costs: `local-only` from 79% visible to 0% at 390×350.
- [ ] 5.3 Assert capture renders identically on a non-cloud profile — byte for
      byte where it can be, by screenshot where it cannot.

## 6. The container

- [ ] 6.1 A Dockerfile carrying `config/models.toml`, the built export, and a
      database seeded at image build time.
- [ ] 6.2 `SECOND_SHIFT_SYNTHETIC=1`, `SECOND_SHIFT_PROFILE=cloud`.
- [ ] 6.3 It must not carry the brain, a real database, or payloads.
- [ ] 6.4 Build it and run it locally. A deploy target verified only on paper is
      not verified.

## 7. Synthetic containment, enforced

- [ ] 7.1 Migration: `is_synthetic` on the eval tables; the runner sets it from
      the deployment, never from a request; the views exclude it.
- [ ] 7.2 A check that a deployment package carries no `model_call_payloads`,
      **and a test proving that check can fail.**
- [ ] 7.3 Fix the README recipe.

## 8. Verify and close

- [ ] 8.1 Full gate. Every new test shown able to fail, with the mutation named.
- [ ] 8.2 Stand up the container, open all three surfaces, **read the
      screenshots**, and report what a stranger said the product was — their
      words.
- [ ] 8.3 On the Spark: a real night, and confirm its timeline renders. This is
      the only way group 2 is actually proven, and it needs the machine.
- [ ] 8.4 Sync, archive, roadmap, and record anything deferred in the next
      capability's entry rather than only here.
