// The night timeline's view model.
//
// Everything here is a pure function over the read contract, kept separate from
// the component so the parts that can be wrong are the parts that are tested.
// Layout arithmetic, lane packing and wall-clock formatting all have a correct
// answer; whether the result feels like game film does not, and no test will
// tell us.

export interface TimelineEvent {
  id: number;
  ts_ms: number;
  lane: string;
  kind: string;
  label: string;
  severity: "debug" | "info" | "warn" | "error";
  duration_ms: number | null;
  agent_invocation_id: string | null;
  model_call_id: string | null;
  is_synthetic: boolean;
}

export interface TimelinePage {
  events: TimelineEvent[];
  next_ts_ms: number | null;
  next_id: number | null;
}

export interface Lane {
  lane: string;
  role: string | null;
  invocations: number;
}

export interface Stage {
  stage: string;
  seq: number;
  status: string;
  started_at_ms: number | null;
  ended_at_ms: number | null;
}

export interface Capture {
  id: string;
  created_at_ms: number;
  title: string | null;
  policy: string;
}

export interface Spend {
  spend_usd: number;
  total_tokens: number;
  cloud_tokens: number;
  calls: number;
  generated: boolean;
}

export interface RunDetail {
  id: string;
  entry_id: string;
  night_of: string;
  started_at_ms: number;
  ended_at_ms: number | null;
  outcome: string | null;
  furthest_stage: string | null;
  effective_policy: string;
  policy_source: string;
  compute_profile: string;
  is_synthetic: boolean;
  captured_tz: string;
  tz_offset_min: number;
  lat: number | null;
  lon: number | null;
  entry_title: string | null;
  extent_start_ms: number | null;
  extent_end_ms: number | null;
  lanes: Lane[];
  stages: Stage[];
  captures: Capture[];
  spend: Spend;
}

/** Below this a bar is indistinguishable from a tick, so it is drawn as one. */
export const MIN_BAR_PX = 3;

/** A night with no extent still needs an axis to divide by. Five minutes. */
export const MIN_SPAN_MS = 5 * 60 * 1000;

export interface Extent {
  start_ms: number;
  end_ms: number;
}

/**
 * The span the axis covers.
 *
 * Ends at the last bar rather than the last instant: work near the end of a
 * night runs past its final recorded timestamp — by over an hour in a real
 * generated night — and an axis built from timestamps alone silently clips it.
 *
 * A run with no events, one event, or several at one instant would otherwise
 * produce a zero-width axis and divide by it.
 */
export function extentOf(run: RunDetail, events: TimelineEvent[] = []): Extent {
  let start = run.extent_start_ms ?? run.started_at_ms;
  let end = run.extent_end_ms ?? run.started_at_ms;

  for (const e of events) {
    if (e.ts_ms < start) start = e.ts_ms;
    const finish = e.ts_ms + (e.duration_ms ?? 0);
    if (finish > end) end = finish;
  }

  if (end - start < MIN_SPAN_MS) end = start + MIN_SPAN_MS;
  return { start_ms: start, end_ms: end };
}

/** Pixels per millisecond for a window of the axis. */
export function scaleFor(window: Extent, width: number): number {
  const span = Math.max(1, window.end_ms - window.start_ms);
  return width / span;
}

export interface PlacedEvent {
  event: TimelineEvent;
  x: number;
  width: number;
  /** Sub-row within the lane. Zero unless the lane has overlapping work. */
  row: number;
  isBar: boolean;
}

/**
 * Place one lane's events, packing overlaps into sub-rows.
 *
 * Bars overlap within a lane by construction, not by accident: agents dispatched
 * together run together, and a stage lead's bar spans the entire window its
 * children occupy. Drawn on one row they cover each other, and the lane reads as
 * a single long bar with nothing in it.
 *
 * Events are assigned to the first row whose last bar has ended. Ticks never
 * push a row — they have no extent to collide with, and giving them one would
 * make a burst of instantaneous writes look like concurrent work.
 */
export function packLane(
  events: TimelineEvent[],
  window: Extent,
  width: number,
): PlacedEvent[] {
  const pxPerMs = scaleFor(window, width);
  const rowEnds: number[] = [];
  const placed: PlacedEvent[] = [];

  for (const event of [...events].sort((a, b) => a.ts_ms - b.ts_ms || a.id - b.id)) {
    const x = (event.ts_ms - window.start_ms) * pxPerMs;
    const rawWidth = (event.duration_ms ?? 0) * pxPerMs;
    const isBar = event.duration_ms != null && rawWidth >= MIN_BAR_PX;
    const drawnWidth = isBar ? rawWidth : MIN_BAR_PX;

    let row = 0;
    if (isBar) {
      // First row free at this instant. Bars are already in time order, so a row
      // whose last bar ended before this one starts can hold it.
      row = rowEnds.findIndex((end) => end <= event.ts_ms);
      if (row === -1) row = rowEnds.length;
      rowEnds[row] = event.ts_ms + (event.duration_ms ?? 0);
    }

    placed.push({ event, x, width: drawnWidth, row, isBar });
  }
  return placed;
}

/** How many sub-rows a packed lane needs. */
export function rowCount(placed: PlacedEvent[]): number {
  return placed.reduce((most, p) => Math.max(most, p.row + 1), 1);
}

/**
 * Wall-clock time where the idea was captured.
 *
 * Built from the offset stored at capture, never from the zone name. Resolving
 * an IANA zone at read time gives the wrong hour for half the year, which is
 * exactly why the offset is recorded at capture in the first place.
 */
export function wallClock(ts_ms: number, tz_offset_min: number): string {
  const shifted = new Date(ts_ms + tz_offset_min * 60_000);
  const hh = String(shifted.getUTCHours()).padStart(2, "0");
  const mm = String(shifted.getUTCMinutes()).padStart(2, "0");
  return `${hh}:${mm}`;
}

/** The same instant, spoken rather than displayed — for the playhead's label. */
export function spokenClock(ts_ms: number, tz_offset_min: number): string {
  const shifted = new Date(ts_ms + tz_offset_min * 60_000);
  const hh = String(shifted.getUTCHours()).padStart(2, "0");
  const mm = String(shifted.getUTCMinutes()).padStart(2, "0");
  const ss = String(shifted.getUTCSeconds()).padStart(2, "0");
  return `${hh}:${mm}:${ss} local`;
}

/** Evenly spaced axis ticks, on whole minutes where the span allows. */
export function axisTicks(window: Extent, count = 6): number[] {
  const span = window.end_ms - window.start_ms;
  const step = span / Math.max(1, count - 1);
  return Array.from({ length: count }, (_, i) => window.start_ms + i * step);
}

export interface PlayheadPosition {
  /** Absolute instant. Not a fraction: the deferred sky layer needs a real time. */
  ts_ms: number;
  tz_offset_min: number;
  lat: number | null;
  lon: number | null;
}

/** Where the playhead sits, in the form anything downstream needs. */
export function playheadAt(run: RunDetail, ts_ms: number): PlayheadPosition {
  return {
    ts_ms,
    tz_offset_min: run.tz_offset_min,
    lat: run.lat,
    lon: run.lon,
  };
}

/** Events at an instant: ticks at it, bars spanning it. */
export function eventsAt(events: TimelineEvent[], ts_ms: number, tolerance_ms = 1000) {
  return events.filter((e) => {
    const end = e.ts_ms + (e.duration_ms ?? 0);
    return e.ts_ms <= ts_ms + tolerance_ms && end >= ts_ms - tolerance_ms;
  });
}

/**
 * A stage's span, bounded when it is still running.
 *
 * Every generated night ends with a stage in flight and a run with no end. That
 * is the state "no empty mornings" describes, and it must render as a correct
 * partial rather than as an unbounded band or an error.
 */
export function stageSpan(stage: Stage, extent: Extent): Extent | null {
  if (stage.started_at_ms == null) return null;
  return {
    start_ms: stage.started_at_ms,
    end_ms: stage.ended_at_ms ?? extent.end_ms,
  };
}

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "";

async function get<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, { signal });
  if (!response.ok) {
    throw new Error(`${path} returned ${response.status}`);
  }
  return (await response.json()) as T;
}

export interface RunSummary {
  id: string;
  night_of: string;
  started_at_ms: number;
  ended_at_ms: number | null;
  outcome: string | null;
  effective_policy: string;
  is_synthetic: boolean;
}

export const fetchRuns = (signal?: AbortSignal) => get<RunSummary[]>("/runs", signal);

export const fetchRun = (runId: string, signal?: AbortSignal) =>
  get<RunDetail>(`/runs/${encodeURIComponent(runId)}`, signal);

/**
 * Every event in a run, followed to the end of the cursor.
 *
 * A real night is over a thousand events and the route windows them, so the view
 * pages rather than assuming one response holds the night. The loop is bounded:
 * a cursor that stops advancing is a server bug, and hanging on it forever hides
 * that instead of surfacing it.
 */
export async function fetchAllEvents(
  runId: string,
  signal?: AbortSignal,
  pageSize = 500,
): Promise<TimelineEvent[]> {
  const events: TimelineEvent[] = [];
  let after: { ts_ms: number; id: number } | null = null;

  for (let page = 0; page < 200; page += 1) {
    const query = new URLSearchParams({ limit: String(pageSize) });
    if (after) {
      query.set("after_ts_ms", String(after.ts_ms));
      query.set("after_id", String(after.id));
    }
    const got = await get<TimelinePage>(
      `/runs/${encodeURIComponent(runId)}/timeline?${query}`,
      signal,
    );
    events.push(...got.events);
    if (got.next_ts_ms == null || got.next_id == null) return events;
    after = { ts_ms: got.next_ts_ms, id: got.next_id };
  }
  throw new Error("timeline paging did not terminate");
}

export const fetchEvent = (eventId: number, signal?: AbortSignal) =>
  get<{
    event: TimelineEvent;
    payload_json: string | null;
    model_call: Record<string, unknown> | null;
  }>(`/events/${eventId}`, signal);
