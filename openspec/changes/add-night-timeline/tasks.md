## 0. Migration 0003

The first migration against a database holding real captured ideas. It runs
against four rows today and against a week of them by Friday.

- [x] 0.1 Add `events.model_call_id` as a nullable foreign key, with an index supporting lookup from an event.
- [x] 0.2 Record the link wherever a model call produces an event, so the column is populated going forward rather than only for newly generated nights.
- [x] 0.3 Populate it in the night generator, so a seeded night exercises hover.
- [x] 0.4 Test: the migration applies to a fresh database and to one already at version 2, with integrity intact.
- [x] 0.5 Test: two calls sharing one instant resolve to their own events, not to whichever is found first.
- [x] 0.6 Test: an event with no call behind it reports none rather than the nearest.

## 1. Repository reads

- [x] 1.1 `timeline` accepts a time window and a page cursor on `(ts_ms, id)`, and carries the generated flag in its projection.
- [ ] 1.2 `invocation_tree` joins the agent roster so each invocation reports its role — the column that decides its lane, and which the current query cannot return.
- [ ] 1.3 Add a lane roster derived from the whole run rather than from a window.
- [ ] 1.4 Add run listing and run detail, joining the entry for its capture offset and location.
- [ ] 1.5 Add a read for the entries captured before a run, for the gutter beside the axis.
- [ ] 1.6 Add stage reads for the band overlay, including a stage still running.
- [ ] 1.7 Add a bucketed read for zoomed-out display, carrying the strongest severity per bucket.
- [ ] 1.8 Add a night cost summed from recorded model calls rather than from views that exclude generated rows.
- [ ] 1.9 Test: ordering survives identifier inversions, verified against a generated night.
- [ ] 1.10 Test: paging returns every event once, including events sharing a timestamp.
- [ ] 1.11 Test: the axis extent covers bars that end after the last recorded instant.
- [ ] 1.12 Test: the lane roster is unchanged by which window is loaded.
- [ ] 1.13 Test: a bucket containing one error reports as an error.

## 2. API surface

- [ ] 2.1 Add the read routes, registered **before** the static mount so they are not swallowed by the fallback.
- [ ] 2.2 Add the deployment label to the capability response, so a demonstration can say it is one.
- [ ] 2.3 Test: routes return the documented columns and reject an unknown run.
- [ ] 2.4 Test: a route added after the static mount would be unreachable — asserted so the ordering cannot silently regress.
- [ ] 2.5 Test: a synthetic deployment reports itself as a demonstration.

## 3. The timeline

- [ ] 3.1 A query-string night route, because static export cannot enumerate run ids.
- [ ] 3.2 Render lanes from the roster, with sub-row packing so overlapping work stays visible.
- [ ] 3.3 Render bars and ticks distinguishably, with a minimum bar width when zoomed out.
- [ ] 3.4 Render events carrying no invocation, since they are the run's skeleton.
- [ ] 3.5 Render the evening's captures in a gutter before the axis, not scrubable and visually distinct from run work.
- [ ] 3.6 Render a run still in flight as a correct partial.
- [ ] 3.7 Axis labels in the entry's recorded capture offset, not the viewer's.
- [ ] 3.8 Playhead exposing an absolute instant and the night's location.
- [ ] 3.9 Slider semantics, keyboard scrubbing, an announced moment, and a text-equivalent event reading.
- [ ] 3.10 Honor reduced-motion by disabling automatic playback while keeping scrubbing.
- [ ] 3.11 Position playback from wall-clock time rather than accumulated frames, so backgrounding does not cause a jump.
- [ ] 3.12 Label generated rows and generated cost as generated.

## 4. Verification

- [ ] 4.1 Test: hover reports the call that produced the event, exactly.
- [ ] 4.2 Test: scrubbing to a moment shows the events at that moment and not others.
- [ ] 4.3 Test: a dense night renders without any payload being parsed.
- [ ] 4.4 Test: keyboard scrubbing moves the playhead and announces the moment.
- [ ] 4.5 Test: frame time at 20x asserted against the measured budget.
- [ ] 4.6 Test: the capture PWA still builds, typechecks and passes its tests.
- [ ] 4.7 Look at it in a browser at several points in the night, and report what was seen rather than what was built.
- [ ] 4.8 Gates: full suite, typecheck, both check scripts, strict validation.
