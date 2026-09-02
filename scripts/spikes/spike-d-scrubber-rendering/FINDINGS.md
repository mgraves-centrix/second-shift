# Spike D — DOM or canvas for the night scrubber

**Question:** can DOM hold 60fps rendering a real generated night at 20x, or does
the scrubber need canvas?

`docs/WEEK_ONE.md` records the abort criterion — if 60fps is not reachable with
DOM, move to canvas — and `docs/prompts/NIGHT_SCRUBBER.md` says not to decide it
by preference. Measured 2026-09-02.

**Answer: DOM, comfortably, and the reason is not the one the criterion
anticipated.**

## Method

One real night from the generator, seed 42, read through
`Repository.timeline(run_id)` — scalar columns only, exactly what a renderer
receives. 1,223 events across 7 lanes over 7.32 hours; 1,019 carry `duration_ms`
and render as bars, 204 as ticks.

Three renderers over identical data and identical playhead motion, in headless
Chromium:

- **dom-incremental** — 1,223 absolutely positioned nodes built once; each frame
  touches only the nodes the playhead crossed since the last one.
- **dom-naive** — writes to every node every frame. Included because it is the
  failure mode the quality bar names by hand, and a number for it is worth more
  than a warning about it.
- **canvas** — clear and redraw every mark each frame.

The playhead advances by wall-clock time at 20x, so the measurement tracks the
motion a viewer would see rather than a fixed step. **A layout property is read
inside the measured window**, which forces style and layout to happen there. Without
that the DOM modes look almost free: their writes are queued and the browser does
the work after the callback returns, so the number would measure how fast the
writes were recorded rather than what they cost.

The first frames pay for the initial layout of freshly created nodes. That is a
real cost and a one-time one, so it is reported separately rather than folded
into `max`, where it would read as a stall that recurs.

## Results

Milliseconds inside the frame. Budget is 16.7ms for 60fps.

**The real night — 1,223 events, 7 lanes:**

| | steady p50 | p95 | max | first frame |
|---|---|---|---|---|
| dom-incremental | 0.1 | 0.2 | **0.3** | 8.8 |
| dom-naive | 0.7 | 1.1 | 1.8 | 9.3 |
| canvas | 0.3 | 0.4 | 2.0 | 0.3 |

**4x stress — 4,892 events, 28 lanes:**

| | steady p50 | p95 | max | first frame |
|---|---|---|---|---|
| dom-incremental | 0.1 | 0.2 | **0.3** | 32.9 |
| dom-naive | 2.4 | 4.0 | 8.2 | 36.0 |
| canvas | 1.0 | 2.2 | 5.4 | 1.2 |

**8x stress — 9,784 events, 56 lanes:**

| | steady p50 | p95 | max | first frame |
|---|---|---|---|---|
| dom-incremental | 0.1 | 0.2 | **0.3** | 69.2 |
| dom-naive | 4.6 | 6.0 | 14.0 | 68.2 |
| canvas | 2.0 | 3.6 | 5.9 | 4.9 |

All three hold 60fps on the real night. Every approach is inside budget; the
question is which one has headroom and where each one's cost goes.

## The finding that matters: the costs scale in opposite directions

**Incremental DOM's steady frame cost does not grow with the night.** 0.1ms at
1,223 events, 0.1ms at 9,784. Its work is proportional to events *crossed per
frame*, which is a function of playback speed and event density in the crossed
window — not of how many events exist.

**Canvas's cost grows linearly with the night**, because it redraws everything
every frame: 0.3ms → 1.0ms → 2.0ms. At 8x it is 20x more expensive per frame than
incremental DOM.

That inverts the usual intuition, and it is the whole answer. Canvas is the
approach that gets into trouble as nights get denser; the reason to reach for it
here would have been an eight-hour night with a hundred thousand events, and this
system generates roughly a thousand.

Two costs DOM does carry, both bounded and both known:

- **Initial layout: 8.8ms** at the real night, 69ms at 8x. Paid once at mount,
  never during a drag.
- **A full-span drag in one frame** crosses every event at once, so incremental
  degenerates to naive's cost for that frame: **1.8ms** at the real night, 14ms
  at 8x. Inside budget at the size this system produces, and the abort criterion
  if nights ever get much denser.

## Decision

**DOM.** It holds 60fps with two orders of magnitude of headroom on the real
night, its steady cost is flat in night size where canvas's is linear, and it
brings hit testing, focus, keyboard interaction and screen-reader semantics at no
cost — all of which `docs/prompts/NIGHT_SCRUBBER.md` requires and none of which
this measurement prices, because canvas would have to implement them by hand.

Ship incremental, not naive. Naive holds 60fps today at 1.8ms, so the difference
is not correctness — it is 6x the cost for no benefit, and 14ms at 8x is close
enough to the budget to be a real ceiling.

## What this does not measure

Script, style and layout, inside headless Chromium on x86 server hardware. Not
paint or composite, and not the target machine or a phone. A layout that is cheap
to compute can still be expensive to paint, and the honest check on that is
looking at it on the device.

## An unrelated finding, from the same data

At a full-night zoom on 1,200px, one pixel is 22 seconds. The median bar is
**1.4px wide** — indistinguishable from a tick. p95 is 62px and the longest is
233px, so the long crawls read fine and the ordinary ones do not.

`duration_ms` non-null versus null is the difference between a forty-second crawl
and an instantaneous write, and the prompt requires it be visible at a glance. At
full-night zoom, width alone cannot carry it. A bar needs a minimum width and a
tick needs to differ in *shape*, not just in size — or the view needs to zoom.

## Reproducing

```bash
apps/api/.venv/bin/python -m secondshift_seed --seed 42 --db <db>
apps/api/.venv/bin/python scripts/spikes/spike-d-scrubber-rendering/export_night.py \
    --db <db> --out <json>
node scripts/spikes/spike-d-scrubber-rendering/measure.mjs --data <json> --frames 400 --scale 1
```

Playwright is imported by name; where it is installed globally, set
`PLAYWRIGHT_MODULE` to its entry point and `PLAYWRIGHT_CHROMIUM` to a browser
binary.
