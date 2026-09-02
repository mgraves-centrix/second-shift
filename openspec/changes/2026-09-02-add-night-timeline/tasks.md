## 1. Reading a night

- [ ] 1.1 List recorded runs through the repository — id, night, span, effective policy, outcome, and whether the run is synthetic.
- [ ] 1.2 Read one event's detail: its payload, and the model call joined through its invocation.
- [ ] 1.3 Test: a run with no model call behind an event reports that, rather than omitting the field.
- [ ] 1.4 Test: the run listing carries `is_synthetic` for every run.

## 2. The routes

Depends on group 1.

- [ ] 2.1 `GET /runs` — recorded nights, newest first.
- [ ] 2.2 `GET /runs/{id}/timeline` — every event's scalar columns, the lanes they recorded, the invocation tree, and the run's frame, in one response.
- [ ] 2.3 `GET /events/{id}` — one event's payload and its model call.
- [ ] 2.4 Refuse an unknown run and an unknown event with a stated reason rather than an empty result.
- [ ] 2.5 Test: the timeline response carries no payload for any event.
- [ ] 2.6 Test: a generated night is returned in full — every event, and the lanes it actually recorded.
- [ ] 2.7 Test: an unknown run is distinguishable from a night in which nothing happened.
- [ ] 2.8 Test: no route added here mutates a row.

## 3. The scrubber

Depends on group 2. Rendering approach settled by Spike D: incremental DOM.

- [ ] 3.1 Fetch a run's timeline once and lay it out — lanes vertical, time horizontal, the full night in view.
- [ ] 3.2 Draw a duration as a bar and its absence as a tick, distinguished by shape so a sub-pixel duration still reads as a bar.
- [ ] 3.3 Render severity, so a failure is visible without interaction.
- [ ] 3.4 Move the playhead by pointer drag, updating only what the playhead crossed rather than the whole timeline.
- [ ] 3.5 Move the playhead by keyboard, and announce the moment politely.
- [ ] 3.6 Show the run's outcome and label a synthetic night as synthetic.
- [ ] 3.7 Fetch one event's detail on hover or focus, and show the model, tokens and cost behind it.
- [ ] 3.8 Represent invocation nesting within a lane.

## 4. Verification

- [ ] 4.1 Test: scrubbing to an instant shows the events at that instant and not others.
- [ ] 4.2 Test: the component never reads a payload from timeline data.
- [ ] 4.3 Test: keyboard scrubbing moves the playhead and updates what is announced.
- [ ] 4.4 Test: a sub-pixel duration is still rendered as a bar.
- [ ] 4.5 Test: an event with no model call renders as having none rather than as free.
- [ ] 4.6 Look at it in a browser against the real generated night, at several points in the night, and report what was seen rather than what was built.
- [ ] 4.7 Confirm the capture path still works after the change — it is taking real ideas.

## 5. Gates

- [ ] 5.1 Gate: full Python suite passes.
- [ ] 5.2 Gate: web tests and typecheck pass, with no `any`.
- [ ] 5.3 Gate: `openspec validate --strict` for this change and every canonical spec.
- [ ] 5.4 Gate: both check scripts pass.
- [ ] 5.5 Gate: the new tests fail with the implementation reverted.
