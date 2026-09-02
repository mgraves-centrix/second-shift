// The night, as geometry.
//
// Everything that decides where a mark goes lives here rather than in the
// component, because it is the part that can be wrong in a way nobody sees. A
// bar one pixel narrower than a tick, an event in the wrong lane, a playhead
// that reports an instant it is not on — none of those throw, and all of them
// are testable as arithmetic.
//
// Nothing here reads a payload. The timeline response has no field for one:
// detail is fetched for the single event a person is looking at, never for the
// thousand a frame is drawn from.

export interface TimelineEvent {
  id: number;
  ts_ms: number;
  lane: string;
  kind: string;
  label: string;
  severity: string;
  duration_ms: number | null;
  agent_invocation_id: string | null;
}

export interface InvocationNode {
  id: string;
  parent_invocation_id: string | null;
  depth: number;
  stage: string | null;
  outcome: string | null;
  started_at_ms: number;
  ended_at_ms: number | null;
}

export interface RunSummary {
  id: string;
  night_of: string;
  started_at_ms: number;
  ended_at_ms: number | null;
  effective_policy: string;
  compute_profile: string;
  outcome: string | null;
  furthest_stage: string | null;
  is_synthetic: boolean;
  first_event_ms: number | null;
  // The last event's END, not its start: the longest bar in a generated night
  // begins over an hour before the last event starts and runs past it.
  last_event_end_ms: number | null;
  event_count: number;
  captured_tz: string | null;
  tz_offset_min: number | null;
}

export interface RunStage {
  stage: string;
  seq: number;
  status: string;
  started_at_ms: number | null;
  ended_at_ms: number | null;
}

export interface Timeline {
  run: RunSummary;
  stages: RunStage[];
  lanes: string[];
  events: TimelineEvent[];
  invocations: InvocationNode[];
}

export interface ModelCall {
  id: string;
  ts_ms: number;
  provider: string;
  model: string;
  policy: string;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  estimated_cost_usd: number | null;
  latency_ms: number | null;
}

export interface EventDetail extends TimelineEvent {
  run_id: string | null;
  payload: Record<string, unknown> | null;
  model_calls: ModelCall[];
}

/** A mark's geometry, computed once at layout rather than per frame. */
export interface Mark {
  event: TimelineEvent;
  /** Left edge, as a fraction of the night's width. */
  x: number;
  /** Width, as a fraction of the night's width. Zero for a tick. */
  w: number;
  lane: number;
  /** Nesting of the invocation that produced it, or zero where none did. */
  depth: number;
  bar: boolean;
  severe: boolean;
}

export interface Night {
  run: RunSummary;
  stages: RunStage[];
  lanes: string[];
  marks: Mark[];
  /** First instant, and the instant the last event *ends*. */
  from: number;
  to: number;
  span: number;
  /** The zone the night is read in. The entry's, never the viewer's. */
  timeZone: string;
}

/**
 * A bar's minimum width, as a fraction of the night.
 *
 * Spike D measured the reason: at a full-night zoom on 1200px, one pixel is 22
 * seconds and the median duration is 1.4px. Without a floor, most bars would be
 * narrower than the ticks they must be distinguishable from — and the
 * difference between a forty-second crawl and an instantaneous write is one of
 * the few things this view exists to show.
 *
 * Shape carries the rest: a tick is drawn as a tick, not as a very short bar.
 */
export const MIN_BAR_FRACTION = 0.0025;

const SEVERE = new Set(["warn", "error"]);

/**
 * Lay a night out once.
 *
 * Fractions rather than pixels, so the same layout survives a resize without
 * being recomputed — a scrubber that relaid out on every resize observation
 * would stutter on the one interaction it exists for.
 */
export function layoutNight(timeline: Timeline): Night {
  const events = [...timeline.events].sort((a, b) => a.ts_ms - b.ts_ms || a.id - b.id);
  const from = events.length ? events[0].ts_ms : timeline.run.started_at_ms;
  // The frame ends where the last event ends, not where the last one starts.
  // A bar that begins near the end still has to fit inside its own night, and
  // `run.ended_at_ms` cannot supply it — nothing closes a run yet, so it is
  // null on every recorded one.
  const to = events.reduce(
    (latest, e) => Math.max(latest, e.ts_ms + (e.duration_ms ?? 0)),
    from,
  );
  const span = Math.max(1, to - from);

  // The lane an event recorded, never the role of whatever produced it: an
  // event may record a lane its producer's role does not match, and a stage
  // boundary has no producer at all.
  const lanes = timeline.lanes.length
    ? timeline.lanes
    : [...new Set(events.map((e) => e.lane))].sort();
  const laneIndex = new Map(lanes.map((lane, index) => [lane, index]));
  const depths = new Map(timeline.invocations.map((i) => [i.id, i.depth]));

  const marks = events.map((event) => {
    const bar = event.duration_ms !== null;
    return {
      event,
      x: (event.ts_ms - from) / span,
      w: bar ? Math.max(MIN_BAR_FRACTION, (event.duration_ms as number) / span) : 0,
      lane: laneIndex.get(event.lane) ?? 0,
      depth: event.agent_invocation_id ? (depths.get(event.agent_invocation_id) ?? 0) : 0,
      bar,
      severe: SEVERE.has(event.severity),
    };
  });

  return {
    run: timeline.run,
    stages: timeline.stages,
    lanes,
    marks,
    from,
    to,
    span,
    // The entry's zone, never the viewer's. A night is a local thing: "the
    // frantic bit at 3am" is a claim about where the person was. UTC is the
    // honest fallback for a run with no entry behind it, and it is labeled.
    timeZone: timeline.run.captured_tz ?? "UTC",
  };
}

/**
 * How far the night actually got.
 *
 * Read from the stages rather than from `run.outcome`, which is null on every
 * recorded run because nothing calls `close_run`. A night that stopped part-way
 * says so here or nowhere, and rendering an absent verdict as a finish is the
 * visual form of hiding partial results.
 */
export function nightProgress(night: Night): {
  complete: number;
  total: number;
  unfinished: RunStage[];
  finished: boolean;
} {
  const total = night.stages.length;
  const complete = night.stages.filter((s) => s.status === "complete").length;
  const unfinished = night.stages.filter(
    (s) => s.status !== "complete" && s.status !== "skipped",
  );
  return { complete, total, unfinished, finished: total > 0 && unfinished.length === 0 };
}

/** The instant a position across the night corresponds to. */
export function instantAt(night: Night, fraction: number): number {
  return night.from + clamp(fraction, 0, 1) * night.span;
}

/** Where an instant sits across the night, as a fraction. */
export function positionOf(night: Night, instant: number): number {
  return clamp((instant - night.from) / night.span, 0, 1);
}

export function clamp(value: number, low: number, high: number): number {
  return value < low ? low : value > high ? high : value;
}

/**
 * The events in progress at an instant.
 *
 * A bar is in progress while the playhead is inside it. A tick has no duration,
 * so it counts as current within a tolerance — otherwise an instantaneous event
 * could only be found by landing on its exact millisecond, and a scrubber moving
 * at 20x steps over 333 of them per frame.
 */
export function eventsAt(night: Night, instant: number, toleranceMs = 1000): TimelineEvent[] {
  return night.marks
    .filter(({ event }) => {
      const end = event.ts_ms + (event.duration_ms ?? 0);
      return instant >= event.ts_ms - toleranceMs && instant <= end + toleranceMs;
    })
    .map((mark) => mark.event);
}

/** How far into the night an instant is, as a fraction, for a progress reading. */
export function elapsedFraction(night: Night, instant: number): number {
  return positionOf(night, instant);
}

/**
 * The moment, in the night's own local framing.
 *
 * A night is a local thing — "the frantic bit at 3am" is a claim about where the
 * person was, not about UTC. The timezone is a fixed argument rather than the
 * browser's, so the same night reads the same whoever opens it.
 */
export function formatMoment(instant: number, timeZone: string): string {
  return new Intl.DateTimeFormat("en-US", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
    timeZone,
  }).format(new Date(instant));
}

/** Arrow keys move by a fraction of the night; shift and page move further. */
export const STEP = 0.002;
export const COARSE = 0.02;

/**
 * Where a key takes the playhead, or null when the key is not ours.
 *
 * Pure, and out of the component, because "keyboard scrubbing works" is a
 * requirement and a component that only answers a pointer is the failure it
 * guards against. The arithmetic is testable; the event plumbing is not.
 */
export function nextPosition(
  current: number,
  key: string,
  shiftKey = false,
): number | null {
  const step = shiftKey ? COARSE : STEP;
  switch (key) {
    case "ArrowRight":
    case "ArrowUp":
      return clamp(current + step, 0, 1);
    case "ArrowLeft":
    case "ArrowDown":
      return clamp(current - step, 0, 1);
    case "PageUp":
      return clamp(current + COARSE, 0, 1);
    case "PageDown":
      return clamp(current - COARSE, 0, 1);
    case "Home":
      return 0;
    case "End":
      return 1;
    default:
      return null;
  }
}

export function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60_000) return `${(ms / 1000).toFixed(1)}s`;
  if (ms < 3_600_000) {
    const minutes = Math.floor(ms / 60_000);
    const seconds = Math.round((ms % 60_000) / 1000);
    return `${minutes}m ${String(seconds).padStart(2, "0")}s`;
  }
  // A night is hours. "506m" is arithmetically fine and nobody reads it.
  const hours = Math.floor(ms / 3_600_000);
  const minutes = Math.round((ms % 3_600_000) / 60_000);
  return `${hours}h ${String(minutes).padStart(2, "0")}m`;
}

export function formatCost(usd: number | null): string {
  if (usd === null) return "unrecorded";
  if (usd === 0) return "$0.00";
  return usd < 0.01 ? `$${usd.toFixed(4)}` : `$${usd.toFixed(2)}`;
}
