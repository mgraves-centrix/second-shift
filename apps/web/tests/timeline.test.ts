// The night timeline's view model.
//
// Layout arithmetic is worth testing because it has a correct answer and fails
// silently: a clipped axis, a lane collapsed onto one row, or an hour shifted by
// a timezone all render as a plausible picture of the wrong night.
//
// How the result actually reads is verified by looking at it in a browser at the
// verification gate. No assertion here substitutes for that.

import assert from "node:assert/strict";
import test from "node:test";

import {
  MIN_BAR_PX,
  MIN_SPAN_MS,
  atEnd,
  axisTicks,
  boundStages,
  captureExtent,
  eventsAt,
  extentOf,
  packLane,
  playheadAt,
  positionAt,
  rowCount,
  scaleFor,
  spokenClock,
  stageSpan,
  wallClock,
  type RunDetail,
  type TimelineEvent,
} from "../lib/timeline.ts";

const T0 = 1_772_000_000_000;

function ev(id: number, offset_ms: number, duration_ms: number | null = null): TimelineEvent {
  return {
    id,
    ts_ms: T0 + offset_ms,
    lane: "lead",
    kind: "agent.start",
    label: `event ${id}`,
    severity: "info",
    duration_ms,
    agent_invocation_id: null,
    model_call_id: null,
    is_synthetic: true,
  };
}

function run(over: Partial<RunDetail> = {}): RunDetail {
  return {
    id: "run-1",
    entry_id: "entry-1",
    night_of: "2026-08-29",
    started_at_ms: T0,
    ended_at_ms: null,
    outcome: null,
    furthest_stage: "draft",
    effective_policy: "local-only",
    policy_source: "entry",
    compute_profile: "spark",
    is_synthetic: true,
    captured_tz: "America/Los_Angeles",
    tz_offset_min: -420,
    lat: null,
    lon: null,
    entry_title: "a night",
    extent_start_ms: T0,
    extent_end_ms: T0 + 3_600_000,
    lanes: [],
    stages: [],
    captures: [],
    spend: { spend_usd: 0, total_tokens: 0, cloud_tokens: 0, calls: 0, generated: true },
    ...over,
  };
}

test("the axis ends at the last bar, not the last timestamp", () => {
  // Work dispatched near the end of a night finishes well after the final
  // recorded instant. An axis built from timestamps alone cuts that bar off.
  const late = ev(1, 3_500_000, 900_000);
  const extent = extentOf(run({ extent_start_ms: T0, extent_end_ms: T0 + 3_500_000 }), [late]);

  assert.equal(extent.end_ms, T0 + 3_500_000 + 900_000);
});

test("a run with no span still yields a divisible axis", () => {
  const extent = extentOf(run({ extent_start_ms: T0, extent_end_ms: T0 }), []);

  assert.equal(extent.end_ms - extent.start_ms, MIN_SPAN_MS);
  assert.ok(Number.isFinite(scaleFor(extent, 800)));
});

test("a single instantaneous event does not divide by zero", () => {
  const extent = extentOf(run({ extent_start_ms: null, extent_end_ms: null }), [ev(1, 0)]);
  const px = scaleFor(extent, 800);

  assert.ok(Number.isFinite(px) && px > 0);
});

test("overlapping bars in one lane are packed onto separate rows", () => {
  // Agents dispatched together run together. Drawn on one row they cover each
  // other and the lane reads as one long empty bar.
  const window = { start_ms: T0, end_ms: T0 + 600_000 };
  const placed = packLane(
    [ev(1, 0, 300_000), ev(2, 60_000, 300_000), ev(3, 120_000, 60_000)],
    window,
    900,
  );

  assert.equal(rowCount(placed), 3);
  assert.deepEqual(placed.map((p) => p.row), [0, 1, 2]);
});

test("a bar reuses a row once the previous one has ended", () => {
  const window = { start_ms: T0, end_ms: T0 + 600_000 };
  const placed = packLane([ev(1, 0, 60_000), ev(2, 120_000, 60_000)], window, 900);

  assert.equal(rowCount(placed), 1);
});

test("ticks never push a lane onto another row", () => {
  // A burst of instantaneous writes is common and is not concurrent work.
  const window = { start_ms: T0, end_ms: T0 + 600_000 };
  const placed = packLane([ev(1, 0), ev(2, 0), ev(3, 0)], window, 900);

  assert.equal(rowCount(placed), 1);
  assert.ok(placed.every((p) => !p.isBar));
});

test("a bar too short to see is drawn as a tick, at a visible width", () => {
  const window = { start_ms: T0, end_ms: T0 + 3_600_000 };
  const [placed] = packLane([ev(1, 0, 5)], window, 900);

  assert.equal(placed.isBar, false);
  assert.equal(placed.width, MIN_BAR_PX);
});

test("a duration of zero stays distinguishable from no duration", () => {
  const window = { start_ms: T0, end_ms: T0 + 600_000 };
  const [zero] = packLane([ev(1, 0, 0)], window, 900);
  const [absent] = packLane([ev(2, 0, null)], window, 900);

  assert.equal(zero.width, MIN_BAR_PX);
  assert.equal(absent.width, MIN_BAR_PX);
});

test("the clock reads in the offset recorded at capture, not the reader's", () => {
  // 07:00 UTC is midnight in an offset of -420. A reader elsewhere must still
  // see the night as it happened where it happened.
  const midnightUtc = Date.UTC(2026, 7, 30, 7, 0, 0);

  assert.equal(wallClock(midnightUtc, -420), "00:00");
  assert.equal(wallClock(midnightUtc, 0), "07:00");
  assert.equal(wallClock(midnightUtc, 330), "12:30");
});

test("the spoken clock carries seconds, so scrubbing is legible", () => {
  const t = Date.UTC(2026, 7, 30, 7, 0, 42);

  assert.equal(spokenClock(t, -420), "00:00:42 local");
});

test("the playhead reports an absolute instant and a position, not a fraction", () => {
  // The deferred sky layer needs a real time and a real place to be built on.
  const at = playheadAt(run({ lat: 47.6, lon: -122.3 }), T0 + 1234);

  assert.equal(at.ts_ms, T0 + 1234);
  assert.equal(at.tz_offset_min, -420);
  assert.deepEqual([at.lat, at.lon], [47.6, -122.3]);
});

test("a missing location is reported as absent rather than as zero", () => {
  // Zero is a real place in the Gulf of Guinea.
  const at = playheadAt(run(), T0);

  assert.equal(at.lat, null);
  assert.equal(at.lon, null);
});

test("an instant selects the bars spanning it and the ticks at it", () => {
  const events = [ev(1, 0, 600_000), ev(2, 300_000), ev(3, 900_000, 60_000)];
  const hits = eventsAt(events, T0 + 300_000).map((e) => e.id);

  assert.deepEqual(hits, [1, 2]);
});

test("a stage still running is bounded by the axis, not left unbounded", () => {
  // Every generated night ends mid-stage. That is the state the system is for.
  const extent = { start_ms: T0, end_ms: T0 + 3_600_000 };
  const span = stageSpan(
    { stage: "draft", seq: 3, status: "running", started_at_ms: T0 + 60_000, ended_at_ms: null },
    extent,
  );

  assert.deepEqual(span, { start_ms: T0 + 60_000, end_ms: extent.end_ms });
});

test("a stage that never started has no band", () => {
  const extent = { start_ms: T0, end_ms: T0 + 3_600_000 };

  assert.equal(
    stageSpan({ stage: "critique", seq: 4, status: "pending", started_at_ms: null, ended_at_ms: null }, extent),
    null,
  );
});

test("axis ticks span the window inclusively", () => {
  const window = { start_ms: T0, end_ms: T0 + 3_600_000 };
  const ticks = axisTicks(window, 5);

  assert.equal(ticks.length, 5);
  assert.equal(ticks[0], window.start_ms);
  assert.equal(ticks[4], window.end_ms);
});

test("events are placed in time order regardless of arrival order", () => {
  // Identifiers are not monotonic in time: nested work is recorded after its
  // siblings and occurs before them.
  const window = { start_ms: T0, end_ms: T0 + 600_000 };
  const placed = packLane([ev(9, 300_000, 1000), ev(2, 60_000, 1000)], window, 900);

  assert.deepEqual(placed.map((p) => p.event.id), [2, 9]);
  assert.ok(placed[0].x < placed[1].x);
});

test("playback position comes from elapsed time, not from frames delivered", () => {
  // A backgrounded tab is throttled to roughly one frame a second. A counter
  // that adds per frame runs slow and the playhead stops meaning the time it
  // claims; anchoring to a monotonic clock costs smoothness instead.
  const extent = { start_ms: T0, end_ms: T0 + 3_600_000 };
  const anchor = { wall_ms: 1000, playhead_ms: T0, rate: 20 };

  // Ten real seconds at 20x is 200 night-seconds, however many frames arrived.
  assert.equal(positionAt(anchor, 11_000, extent), T0 + 200_000);
});

test("playback stops at the end of the night rather than running past it", () => {
  const extent = { start_ms: T0, end_ms: T0 + 3_600_000 };
  const anchor = { wall_ms: 0, playhead_ms: T0, rate: 1000 };

  assert.equal(positionAt(anchor, 60_000, extent), extent.end_ms);
  assert.equal(atEnd(positionAt(anchor, 60_000, extent), extent), true);
});

test("a clock reading before the anchor does not move the playhead backward", () => {
  const extent = { start_ms: T0, end_ms: T0 + 3_600_000 };
  const anchor = { wall_ms: 5000, playhead_ms: T0 + 60_000, rate: 20 };

  assert.equal(positionAt(anchor, 4000, extent), T0 + 60_000);
});

test("a completed stage is bounded by the next one, not by the end of the night", () => {
  // No stage records an end. Bounding each by the axis draws six bands all
  // running to morning, stacked on each other and reading as stripes.
  const extent = { start_ms: T0, end_ms: T0 + 3_600_000 };
  const bound = boundStages(
    [
      { stage: "brief", seq: 1, status: "complete", started_at_ms: T0, ended_at_ms: null },
      { stage: "build", seq: 2, status: "complete", started_at_ms: T0 + 600_000, ended_at_ms: null },
      { stage: "distill", seq: 3, status: "running", started_at_ms: T0 + 1_800_000, ended_at_ms: null },
    ],
    extent,
  );

  assert.deepEqual(bound.map((b) => [b.span.start_ms - T0, b.span.end_ms - T0]), [
    [0, 600_000],
    [600_000, 1_800_000],
    [1_800_000, 3_600_000],
  ]);
});

test("only the final stage is reported as still open", () => {
  const extent = { start_ms: T0, end_ms: T0 + 3_600_000 };
  const bound = boundStages(
    [
      { stage: "brief", seq: 1, status: "complete", started_at_ms: T0, ended_at_ms: null },
      { stage: "distill", seq: 2, status: "running", started_at_ms: T0 + 600_000, ended_at_ms: null },
    ],
    extent,
  );

  assert.deepEqual(bound.map((b) => b.open), [false, true]);
});

test("stage bands are ordered by sequence, not by arrival", () => {
  const extent = { start_ms: T0, end_ms: T0 + 3_600_000 };
  const bound = boundStages(
    [
      { stage: "build", seq: 2, status: "complete", started_at_ms: T0 + 600_000, ended_at_ms: null },
      { stage: "brief", seq: 1, status: "complete", started_at_ms: T0, ended_at_ms: null },
    ],
    extent,
  );

  assert.deepEqual(bound.map((b) => b.stage.stage), ["brief", "build"]);
});

test("a stage that never started contributes no band", () => {
  const extent = { start_ms: T0, end_ms: T0 + 3_600_000 };
  const bound = boundStages(
    [
      { stage: "brief", seq: 1, status: "complete", started_at_ms: T0, ended_at_ms: null },
      { stage: "publish", seq: 2, status: "pending", started_at_ms: null, ended_at_ms: null },
    ],
    extent,
  );

  assert.equal(bound.length, 1);
  assert.equal(bound[0].span.end_ms, extent.end_ms);
});

test("the capture gutter spans the evening before the run, not the run itself", () => {
  // Captures land hours before the work starts. Folded into the main axis they
  // would halve the resolution of the night to make room for an empty evening.
  const captures = [
    { id: "a", created_at_ms: T0 - 17_000_000, title: null, policy: "local-only" },
    { id: "b", created_at_ms: T0 - 1_000_000, title: null, policy: "local-only" },
  ];

  assert.deepEqual(captureExtent(captures, T0), {
    start_ms: T0 - 17_000_000,
    end_ms: T0,
  });
});

test("a night with nothing captured beforehand has no gutter", () => {
  assert.equal(captureExtent([], T0), null);
  assert.equal(
    captureExtent([{ id: "a", created_at_ms: T0 + 5000, title: null, policy: "local-only" }], T0),
    null,
  );
});
