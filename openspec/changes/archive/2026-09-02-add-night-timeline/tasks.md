## 1. Reading a night

- [x] 1.1 List recorded runs with the frame their events occupy, the zone the idea was captured in, and whether the run is synthetic.
- [x] 1.2 Take the frame's end from the last event's *end*, not its start, so a bar that begins near the end still fits inside its night.
- [x] 1.3 Read what each stage reached, because `runs.outcome` is null on every recorded run and nothing calls `close_run`.
- [x] 1.4 Read one event's detail: its payload, and every model call its invocation made.
- [x] 1.5 Test: the frame ends after the longest bar rather than at the last start.
- [x] 1.6 Test: the listing carries the capture timezone and `is_synthetic`.

## 2. The routes

Depends on group 1.

- [x] 2.1 `GET /runs` — recorded nights, newest first.
- [x] 2.2 `GET /runs/{id}/timeline` — every event's scalar columns, the lanes they recorded, the invocation tree, the stages, and the frame, in one response.
- [x] 2.3 `GET /events/{id}` — one event's payload and the model calls of its invocation.
- [x] 2.4 Refuse an unknown run and an unknown event with a stated reason rather than an empty result.
- [x] 2.5 Test: the timeline response carries no payload for any event.
- [x] 2.6 Test: no route serves prompt or completion text, and the response shape has no field one could travel in.
- [x] 2.7 Test: a lane whose only event has no invocation still appears, which a lane set built by joining would drop.
- [x] 2.8 Test: an event whose recorded lane differs from its producer's role is returned in the lane it recorded.
- [x] 2.9 Test: an unknown run is distinguishable from a night in which nothing happened.
- [x] 2.10 Test: reading a night changes no row, and the routes accept no write.

## 3. The scrubber

Depends on group 2. Rendering approach settled by Spike D: incremental DOM.

- [x] 3.1 Fetch a run's timeline once and lay it out — lanes vertical, time horizontal, the full night in view.
- [x] 3.2 Draw a duration as a bar and its absence as a diamond, so a sub-pixel duration still reads as a bar.
- [x] 3.3 Render severity in a color no lane uses, so a healthy lane cannot read as a failed one.
- [x] 3.4 Move the playhead by pointer drag, updating only the marks it crossed.
- [x] 3.5 Move the playhead by keyboard, as a slider that names itself and its position.
- [x] 3.6 Show what the playhead is inside, resolved when it comes to rest rather than every frame.
- [x] 3.7 Show how far the night got from its stages, and label a synthetic night as synthetic.
- [x] 3.8 Fetch one event's detail on hover, aborting a request the next one supersedes.
- [x] 3.9 Render invocation depth as an offset within a lane.
- [x] 3.10 Serve it as one exported page taking the run on the client, so the static export needs no dynamic segment.

## 4. Verification

- [x] 4.1 Test: scrubbing to an instant reports the events in progress there and not others.
- [x] 4.2 Test: a bar is current for its whole duration, not only at its start.
- [x] 4.3 Test: keyboard stepping moves the playhead, clamps at both ends, and does not steal keys that are not ours.
- [x] 4.4 Test: a sub-pixel duration is drawn at the minimum bar width and still as a bar.
- [x] 4.5 Test: a lane is the recorded lane, and depth comes from the tree.
- [x] 4.6 Test: how far the night got is read from the stages, not from the run's empty outcome.
- [x] 4.7 Look at it in a browser against the real generated night, at several points, and report what was seen.
- [x] 4.8 Confirm the capture path still works after the change — captured, replayed idempotently, one row.

## 5. Gates

- [x] 5.1 Gate: full Python suite passes.
- [x] 5.2 Gate: web tests and typecheck pass, with no `any`.
- [x] 5.3 Gate: the static export builds with the night page in it.
- [x] 5.4 Gate: `openspec validate --strict` for this change and every canonical spec.
- [x] 5.5 Gate: both check scripts pass.
- [x] 5.6 Gate: the new tests fail with the implementation reverted — frame from the last start, no minimum bar width, lanes built by joining, and stages dropped were each checked.
