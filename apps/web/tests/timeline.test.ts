// The night, as geometry.
//
// Everything here is arithmetic a person cannot see going wrong: a bar one pixel
// narrower than the tick it must be told apart from, an event in the wrong lane,
// a frame that ends before its longest bar does. Rendering itself is verified by
// looking at it — a test suite cannot tell you whether a scrubber feels right,
// and it can tell you whether the numbers under it are correct.

import assert from "node:assert/strict";
import test from "node:test";

import {
  MIN_BAR_FRACTION,
  eventsAt,
  formatCost,
  formatDuration,
  formatMoment,
  instantAt,
  layoutNight,
  nextPosition,
  nightProgress,
  positionOf,
  type RunStage,
  type Timeline,
  type TimelineEvent,
} from "../lib/timeline.ts";

const T0 = 1_787_893_252_451;
const HOUR = 3_600_000;

function event(over: Partial<TimelineEvent> & { id: number; ts_ms: number }): TimelineEvent {
  return {
    lane: "critic",
    kind: "note",
    label: "an event",
    severity: "info",
    duration_ms: null,
    agent_invocation_id: null,
    ...over,
  };
}

function timeline(
  events: TimelineEvent[],
  over: { lanes?: string[]; stages?: RunStage[]; invocations?: Timeline["invocations"] } = {},
): Timeline {
  return {
    run: {
      id: "01RUN",
      night_of: "2026-08-27",
      started_at_ms: T0,
      ended_at_ms: null,
      effective_policy: "cloud-assisted",
      compute_profile: "spark",
      outcome: null,
      furthest_stage: null,
      is_synthetic: true,
      first_event_ms: T0,
      last_event_end_ms: null,
      event_count: events.length,
      captured_tz: "America/Los_Angeles",
      tz_offset_min: -420,
    },
    stages: over.stages ?? [],
    lanes: over.lanes ?? [...new Set(events.map((e) => e.lane))].sort(),
    events,
    invocations: over.invocations ?? [],
  };
}

test("the frame ends where the last event ends, not where it starts", () => {
  // The real case: the longest bar in a generated night begins over an hour
  // before the last event starts and runs past it.
  const night = layoutNight(
    timeline([
      event({ id: 1, ts_ms: T0 }),
      event({ id: 2, ts_ms: T0 + HOUR, duration_ms: 3 * HOUR }),
      event({ id: 3, ts_ms: T0 + 2 * HOUR }),
    ]),
  );
  assert.equal(night.to, T0 + 4 * HOUR);
  for (const mark of night.marks) {
    assert.ok(mark.x + mark.w <= 1.000001, `${mark.event.id} runs past the night`);
  }
});

test("a duration too short to draw is still drawn as a bar", () => {
  const night = layoutNight(
    timeline([
      event({ id: 1, ts_ms: T0 }),
      event({ id: 2, ts_ms: T0 + HOUR, duration_ms: 900 }),
      event({ id: 3, ts_ms: T0 + 7 * HOUR }),
    ]),
  );
  const tiny = night.marks.find((m) => m.event.id === 2)!;
  assert.equal(tiny.bar, true);
  assert.equal(tiny.w, MIN_BAR_FRACTION);
  assert.ok(tiny.w > (900 / night.span), "the true width would be invisible");
});

test("a tick is not a very short bar", () => {
  const night = layoutNight(
    timeline([
      event({ id: 1, ts_ms: T0 }),
      event({ id: 2, ts_ms: T0 + HOUR, duration_ms: 900 }),
      event({ id: 3, ts_ms: T0 + 7 * HOUR }),
    ]),
  );
  const tick = night.marks.find((m) => m.event.id === 1)!;
  const bar = night.marks.find((m) => m.event.id === 2)!;
  assert.equal(tick.bar, false);
  assert.equal(tick.w, 0);
  assert.notEqual(tick.bar, bar.bar, "shape, not size, is what separates them");
});

test("a long duration is proportional, not clamped", () => {
  const night = layoutNight(
    timeline([
      event({ id: 1, ts_ms: T0, duration_ms: 4 * HOUR }),
      event({ id: 2, ts_ms: T0 + 8 * HOUR }),
    ]),
  );
  const long = night.marks.find((m) => m.event.id === 1)!;
  assert.ok(Math.abs(long.w - 0.5) < 0.001, `expected half the night, got ${long.w}`);
});

test("a lane is the lane the event recorded, even with no invocation behind it", () => {
  const night = layoutNight(
    timeline(
      [
        event({ id: 1, ts_ms: T0, lane: "system", agent_invocation_id: null }),
        event({ id: 2, ts_ms: T0 + HOUR, lane: "critic", agent_invocation_id: "01INV" }),
        // The divergent case: recorded as system, produced by a builder.
        event({ id: 3, ts_ms: T0 + 2 * HOUR, lane: "system", agent_invocation_id: "01INV" }),
      ],
      { lanes: ["critic", "system"], invocations: [
        { id: "01INV", parent_invocation_id: null, depth: 2, stage: "build",
          outcome: "success", started_at_ms: T0, ended_at_ms: null },
      ] },
    ),
  );
  const byId = new Map(night.marks.map((m) => [m.event.id, m]));
  assert.equal(byId.get(1)!.lane, 1, "an event with no invocation keeps its lane");
  assert.equal(byId.get(2)!.lane, 0);
  assert.equal(byId.get(3)!.lane, 1, "the recorded lane wins over the producer's role");
});

test("depth comes from the invocation tree, and is zero without one", () => {
  const night = layoutNight(
    timeline(
      [
        event({ id: 1, ts_ms: T0, agent_invocation_id: null }),
        event({ id: 2, ts_ms: T0 + HOUR, agent_invocation_id: "01DEEP" }),
      ],
      {
        invocations: [
          { id: "01DEEP", parent_invocation_id: "01TOP", depth: 3, stage: "build",
            outcome: "success", started_at_ms: T0, ended_at_ms: null },
        ],
      },
    ),
  );
  const byId = new Map(night.marks.map((m) => [m.event.id, m]));
  assert.equal(byId.get(1)!.depth, 0);
  assert.equal(byId.get(2)!.depth, 3);
});

test("scrubbing to an instant shows the events there and not others", () => {
  const night = layoutNight(
    timeline([
      event({ id: 1, ts_ms: T0 }),
      event({ id: 2, ts_ms: T0 + 3 * HOUR, duration_ms: HOUR }),
      event({ id: 3, ts_ms: T0 + 6 * HOUR }),
    ]),
  );
  const inside = eventsAt(night, T0 + 3.5 * HOUR).map((e) => e.id);
  assert.deepEqual(inside, [2], "only the event in progress");

  const between = eventsAt(night, T0 + 5 * HOUR).map((e) => e.id);
  assert.deepEqual(between, [], "an instant no event covers shows none");

  assert.deepEqual(eventsAt(night, T0).map((e) => e.id), [1]);
});

test("a bar is current for its whole duration, not only at its start", () => {
  const night = layoutNight(
    timeline([
      event({ id: 1, ts_ms: T0, duration_ms: 2 * HOUR }),
      event({ id: 2, ts_ms: T0 + 5 * HOUR }),
    ]),
  );
  for (const offset of [0, 0.5, 1, 1.9]) {
    assert.deepEqual(
      eventsAt(night, T0 + offset * HOUR).map((e) => e.id),
      [1],
      `expected the bar to be current ${offset}h in`,
    );
  }
  assert.deepEqual(eventsAt(night, T0 + 3 * HOUR).map((e) => e.id), []);
});

test("position and instant round-trip, and clamp at the edges", () => {
  const night = layoutNight(
    timeline([event({ id: 1, ts_ms: T0 }), event({ id: 2, ts_ms: T0 + 8 * HOUR })]),
  );
  assert.equal(instantAt(night, 0), night.from);
  assert.equal(instantAt(night, 1), night.to);
  assert.equal(instantAt(night, -3), night.from, "before the night is the start of it");
  assert.equal(instantAt(night, 9), night.to);
  assert.ok(Math.abs(positionOf(night, instantAt(night, 0.37)) - 0.37) < 1e-9);
});

test("keyboard scrubbing moves the playhead, and only on keys that are ours", () => {
  assert.equal(nextPosition(0.5, "ArrowRight"), 0.502);
  assert.equal(nextPosition(0.5, "ArrowLeft"), 0.498);
  assert.equal(nextPosition(0.5, "ArrowRight", true), 0.52);
  assert.equal(nextPosition(0.5, "Home"), 0);
  assert.equal(nextPosition(0.5, "End"), 1);
  assert.equal(nextPosition(0.5, "Enter"), null, "a key that is not ours is not stolen");
  assert.equal(nextPosition(1, "ArrowRight"), 1, "clamped at the end of the night");
  assert.equal(nextPosition(0, "ArrowLeft"), 0);
});

test("the moment reads in the night's zone, not the process's", () => {
  const night = layoutNight(
    timeline([event({ id: 1, ts_ms: T0 }), event({ id: 2, ts_ms: T0 + HOUR })]),
  );
  assert.equal(night.timeZone, "America/Los_Angeles");
  const local = formatMoment(T0, night.timeZone);
  const utc = formatMoment(T0, "UTC");
  assert.notEqual(local, utc, "a night is read where the person was");
  assert.match(local, /^\d{2}:\d{2}:\d{2}$/);
});

test("how far the night got is read from its stages, not its outcome", () => {
  const stages: RunStage[] = [
    { stage: "brief", seq: 1, status: "complete", started_at_ms: T0, ended_at_ms: null },
    { stage: "distill", seq: 2, status: "running", started_at_ms: T0, ended_at_ms: null },
  ];
  const night = layoutNight(
    timeline([event({ id: 1, ts_ms: T0 }), event({ id: 2, ts_ms: T0 + HOUR })], { stages }),
  );
  assert.equal(night.run.outcome, null, "no recorded run carries one");
  const progress = nightProgress(night);
  assert.equal(progress.finished, false, "an absent verdict is not a good one");
  assert.equal(progress.complete, 1);
  assert.deepEqual(progress.unfinished.map((s) => s.stage), ["distill"]);
});

test("a night whose stages all completed says so", () => {
  const stages: RunStage[] = [
    { stage: "brief", seq: 1, status: "complete", started_at_ms: T0, ended_at_ms: null },
    { stage: "distill", seq: 2, status: "complete", started_at_ms: T0, ended_at_ms: null },
  ];
  const night = layoutNight(timeline([event({ id: 1, ts_ms: T0 })], { stages }));
  assert.equal(nightProgress(night).finished, true);
});

test("costs and durations read as themselves", () => {
  assert.equal(formatCost(null), "unrecorded");
  assert.equal(formatCost(0), "$0.00");
  assert.equal(formatCost(0.0004), "$0.0004");
  assert.equal(formatCost(1.5), "$1.50");
  assert.equal(formatDuration(735), "735ms");
  assert.equal(formatDuration(31_135), "31.1s");
  assert.equal(formatDuration(3_599_000), "59m 59s");
  // A night is hours. "506m" is arithmetically fine and nobody reads it.
  assert.equal(formatDuration(5_121_279), "1h 25m");
  assert.equal(formatDuration(30_390_064), "8h 27m");
});
