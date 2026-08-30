"use client";

// Game film for a night.
//
// The point of this view is that a night the assistant spent hours on can be
// read in a minute: where it went wide, where it stalled, where it gave up. It
// is read-only by construction — nothing here writes, so it can be opened
// against a live database without a second thought.
//
// The run is chosen by query string rather than by a dynamic route because the
// site is exported statically; a path segment would need every run enumerated
// at build time, and runs are created nightly.

import { useCallback, useEffect, useMemo, useState } from "react";

import {
  axisTicks,
  extentOf,
  eventsAt,
  fetchAllEvents,
  fetchRun,
  fetchRuns,
  packLane,
  rowCount,
  scaleFor,
  spokenClock,
  stageSpan,
  wallClock,
  type Extent,
  type PlacedEvent,
  type RunDetail,
  type TimelineEvent,
} from "../../lib/timeline.ts";
import styles from "./night.module.css";

const TRACK_PX = 1200;
const LANE_PX = 24;

export default function NightPage() {
  const [run, setRun] = useState<RunDetail | null>(null);
  const [events, setEvents] = useState<TimelineEvent[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [playheadMs, setPlayheadMs] = useState<number | null>(null);
  const [selected, setSelected] = useState<TimelineEvent | null>(null);

  useEffect(() => {
    const abort = new AbortController();

    (async () => {
      try {
        const wanted = new URLSearchParams(window.location.search).get("run");
        // Without an explicit run, show the most recent one. Opening the view
        // and being asked to pick from a list is friction on the one screen
        // meant to be glanced at.
        const runId = wanted ?? (await fetchRuns(abort.signal))[0]?.id;
        if (!runId) {
          setLoading(false);
          return;
        }
        const [detail, all] = await Promise.all([
          fetchRun(runId, abort.signal),
          fetchAllEvents(runId, abort.signal),
        ]);
        setRun(detail);
        setEvents(all);
        setPlayheadMs(detail.extent_start_ms ?? detail.started_at_ms);
      } catch (cause) {
        if (!abort.signal.aborted) setError(String(cause));
      } finally {
        if (!abort.signal.aborted) setLoading(false);
      }
    })();

    return () => abort.abort();
  }, []);

  const extent: Extent | null = useMemo(
    () => (run ? extentOf(run, events) : null),
    [run, events],
  );

  // Packed once per load rather than per frame. A night is over a thousand
  // events and scrubbing repacking them drops frames on the machine this is
  // demonstrated on.
  const lanes = useMemo(() => {
    if (!run || !extent) return [];
    const byLane = new Map<string, TimelineEvent[]>();
    for (const lane of run.lanes) byLane.set(lane.lane, []);
    for (const event of events) {
      const bucket = byLane.get(event.lane);
      if (bucket) bucket.push(event);
      else byLane.set(event.lane, [event]);
    }
    return run.lanes.map((lane) => {
      const placed = packLane(byLane.get(lane.lane) ?? [], extent, TRACK_PX);
      return { lane, placed, rows: rowCount(placed) };
    });
  }, [run, events, extent]);

  const atPlayhead = useMemo(
    () => (playheadMs == null ? [] : eventsAt(events, playheadMs)),
    [events, playheadMs],
  );

  const onScrub = useCallback((value: number) => {
    setPlayheadMs(value);
  }, []);

  if (loading) return <main className={styles.page}><p className={styles.empty}>Reading the night…</p></main>;
  if (error) return <main className={styles.page}><p className={styles.error}>{error}</p></main>;
  if (!run || !extent) {
    return (
      <main className={styles.page}>
        <p className={styles.empty}>No runs recorded yet.</p>
      </main>
    );
  }

  const pxPerMs = scaleFor(extent, TRACK_PX);
  const at = (ts: number) => (ts - extent.start_ms) * pxPerMs;
  const tz = run.tz_offset_min;
  const playheadX = playheadMs == null ? 0 : at(playheadMs);

  return (
    <main className={styles.page}>
      <header className={styles.head}>
        <div>
          <h1 className={styles.title}>{run.entry_title ?? "Untitled idea"}</h1>
          <p className={styles.subtitle}>
            {run.night_of} · {wallClock(extent.start_ms, tz)}–{wallClock(extent.end_ms, tz)} {run.captured_tz}
            {run.ended_at_ms == null && " · still running"}
          </p>
        </div>
        <div className={styles.facts}>
          <span className={styles.fact}>{run.effective_policy}</span>
          <span className={styles.fact}>{run.compute_profile}</span>
          <span className={styles.fact}>{run.furthest_stage ?? "no stage"}</span>
          <span className={styles.fact}>{events.length} events</span>
          <span className={styles.fact}>
            {run.spend.total_tokens.toLocaleString()} tokens · ${run.spend.spend_usd.toFixed(4)}
          </span>
          {(run.is_synthetic || run.spend.generated) && (
            <span className={`${styles.fact} ${styles.synthetic}`}>generated</span>
          )}
        </div>
      </header>

      <div className={styles.scroller}>
        <div className={styles.grid} style={{ width: `calc(var(--label-w) + ${TRACK_PX}px)` }}>
          <div className={styles.rowLabel}>stages</div>
          <div className={styles.stages}>
            {run.stages.map((stage) => {
              const span = stageSpan(stage, extent);
              if (!span) return null;
              return (
                <div
                  key={`${stage.stage}-${stage.seq}`}
                  className={styles.stage}
                  data-open={stage.ended_at_ms == null}
                  style={{ left: at(span.start_ms), width: Math.max(2, (span.end_ms - span.start_ms) * pxPerMs) }}
                  title={`${stage.stage} · ${stage.status}`}
                >
                  {stage.stage}
                </div>
              );
            })}
          </div>

          <div className={styles.rowLabel}>captured</div>
          <div className={styles.captures}>
            {run.captures.map((capture) => (
              <div
                key={capture.id}
                className={styles.capture}
                style={{ left: at(capture.created_at_ms) }}
                title={`${capture.title ?? "untitled"} · ${wallClock(capture.created_at_ms, tz)}`}
              />
            ))}
          </div>

          {lanes.map(({ lane, placed, rows }) => (
            <Lane
              key={lane.lane}
              name={lane.lane}
              role={lane.role}
              invocations={lane.invocations}
              placed={placed}
              rows={rows}
              tz={tz}
              selected={selected}
              onSelect={setSelected}
            />
          ))}

          <div className={styles.rowLabel} />
          <div className={styles.axis}>
            {axisTicks(extent).map((ts) => (
              <span key={ts} className={styles.axisTick} style={{ left: at(ts) }}>
                {wallClock(ts, tz)}
              </span>
            ))}
            {playheadMs != null && <div className={styles.playhead} style={{ left: playheadX }} />}
          </div>
        </div>
      </div>

      <div className={styles.scrubRow}>
        <label className={styles.visuallyHidden} htmlFor="scrub">
          Position in the night
        </label>
        {/* A real range input rather than a reimplemented one: arrow keys, Home,
            End and assistive technology all come with it and none of them would
            survive a hand-rolled drag handler. */}
        <input
          id="scrub"
          className={styles.scrub}
          type="range"
          min={extent.start_ms}
          max={extent.end_ms}
          step={1000}
          value={playheadMs ?? extent.start_ms}
          onChange={(e) => onScrub(Number(e.target.value))}
          aria-valuetext={`${spokenClock(playheadMs ?? extent.start_ms, tz)}, ${atPlayhead.length} events`}
        />
        <span className={styles.moment} aria-live="polite">
          {spokenClock(playheadMs ?? extent.start_ms, tz)}
        </span>
      </div>

      {selected && <Detail event={selected} tz={tz} />}

      <details className={styles.equivalent}>
        <summary>The same night as a list ({events.length} events)</summary>
        <ol>
          {events.map((event) => (
            <li key={event.id}>
              {wallClock(event.ts_ms, tz)} · {event.lane} · {event.label}
              {event.duration_ms != null && ` (${Math.round(event.duration_ms / 1000)}s)`}
              {event.severity !== "info" && ` · ${event.severity}`}
            </li>
          ))}
        </ol>
      </details>
    </main>
  );
}

function Lane({
  name,
  role,
  invocations,
  placed,
  rows,
  tz,
  selected,
  onSelect,
}: {
  name: string;
  role: string | null;
  invocations: number;
  placed: PlacedEvent[];
  rows: number;
  tz: number;
  selected: TimelineEvent | null;
  onSelect: (event: TimelineEvent) => void;
}) {
  const height = rows * LANE_PX;
  return (
    <>
      <div className={styles.rowLabel} style={{ lineHeight: `${height}px` }}>
        {name}
        {role && <em>{role} · {invocations}</em>}
      </div>
      <div className={styles.track} style={{ height }}>
        {placed.map((p) => (
          <button
            key={p.event.id}
            type="button"
            className={styles.mark}
            data-severity={p.event.severity}
            data-bar={p.isBar}
            data-selected={selected?.id === p.event.id}
            style={{
              left: p.x,
              width: p.width,
              top: p.row * LANE_PX + 5,
              height: LANE_PX - 12,
            }}
            onClick={() => onSelect(p.event)}
            title={`${wallClock(p.event.ts_ms, tz)} · ${p.event.label}`}
          >
            <span className={styles.visuallyHidden}>
              {wallClock(p.event.ts_ms, tz)} {p.event.label}
              {p.event.duration_ms != null && `, ${Math.round(p.event.duration_ms / 1000)} seconds`}
            </span>
          </button>
        ))}
      </div>
    </>
  );
}

function Detail({ event, tz }: { event: TimelineEvent; tz: number }) {
  return (
    <section className={styles.detail} aria-live="polite">
      <strong>{event.label}</strong>
      <dl>
        <dt>at</dt>
        <dd>{spokenClock(event.ts_ms, tz)}</dd>
        <dt>lane</dt>
        <dd>{event.lane}</dd>
        <dt>kind</dt>
        <dd>{event.kind}</dd>
        <dt>severity</dt>
        <dd>{event.severity}</dd>
        {event.duration_ms != null && (
          <>
            <dt>took</dt>
            <dd>{(event.duration_ms / 1000).toFixed(1)}s</dd>
          </>
        )}
        {event.model_call_id && (
          <>
            <dt>model call</dt>
            <dd>{event.model_call_id}</dd>
          </>
        )}
        {event.is_synthetic && (
          <>
            <dt>source</dt>
            <dd>generated</dd>
          </>
        )}
      </dl>
    </section>
  );
}
