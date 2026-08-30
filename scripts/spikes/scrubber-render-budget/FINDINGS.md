# Scrubber render budget — DOM or canvas?

**Question:** can DOM nodes hold 60fps while scrubbing a real generated night at
20x, or is canvas required?

**Answer: DOM, comfortably.** Measured 2026-08-28 against the real generated
night — 1,223 events, 7 lanes — not synthetic filler.

| Renderer | mean | p50 | p95 | max |
|---|---|---|---|---|
| DOM | 0.39ms | 0.30ms | 0.60ms | 3.30ms |
| Canvas | 0.05ms | 0.00ms | 0.20ms | 0.20ms |

Budget for 60fps is 16.7ms per frame. 120 frames, scrubbed across the full span,
one-sixth of the night visible at a time, layout forced each frame so the cost is
measured rather than deferred.

## Why DOM, given canvas is seven times faster

Because performance is not the constraint. DOM sits **28x under budget at p95**,
so a device ten times slower than this one still holds 60fps. Choosing canvas
would spend that headroom on nothing and buy back three problems:

- `role="slider"`, `aria-valuetext` and keyboard scrubbing, which a canvas has to
  reimplement from scratch and usually does not
- hit testing for hover, which is the feature that turns the timeline from an
  animation into evidence
- inspectability — a rendering bug in DOM is visible in the element inspector

`docs/WEEK_ONE.md` recorded the abort criterion as "if 60fps is not reachable
with DOM nodes, move to canvas." It is reachable, so the criterion does not fire.

## Honest limits of this measurement

Measured on the development Mac, not on a phone. The scrubber is a desktop and
demo surface rather than a capture surface, and the headroom is wide enough that
this is unlikely to matter — but it was not measured on the target the capture
PWA runs on.

The benchmark draws bars only. It does not measure text labels, lane headers, the
playhead, or hover cards, all of which cost something. It measures the part that
scales with event count, which is the part that decides the question.

Revisit if an event count above ~10,000 per night becomes normal, or if lane
count grows past a few dozen.

## The shipped implementation, measured against this budget

Measured 2026-08-30 against the built night view serving the same generated
night — 1,223 marks in the DOM, seven lanes, the full span stepped in 120
positions with layout forced each step, first pass discarded.

| Build | p50 | p95 | max | frames over 16.7ms |
|---|---|---|---|---|
| First working version | 5.4ms | 7.3ms | 8.1ms | 0 |
| Lanes memoized | 2.2ms | 3.1ms | 6.1ms | 0 |

Both hold the budget. The first version spent a third of every frame rebuilding
1,223 marks that had not changed, because the playhead moves sixty times a second
and React re-rendered the lanes with it. Memoizing the lanes on a stable
selection id — rather than on the selected event object — cut per-frame cost by
well over half.

This is 5x slower than the prototype in the table above, which is expected: the
prototype drew bars into a container, and this renders lane headers, stage bands,
a capture gutter, an axis, focusable marks and their labels. The prototype
answered whether DOM can hold the budget. This answers whether the thing actually
built does, and it does, 5x under at p95.

The benchmark asserts the playhead still moves after the run. A memoization bug
that froze the lanes would otherwise produce excellent numbers for a broken view.

Same limits as above: a development Mac, not a phone.
