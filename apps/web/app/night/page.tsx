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

import { memo, useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  atEnd,
  axisTicks,
  boundStages,
  captureExtent,
  extentOf,
  eventsAt,
  fetchAllEvents,
  fetchRun,
  fetchRuns,
  packLane,
  positionAt,
  rowCount,
  scaleFor,
  spokenClock,
  wallClock,
  type Extent,
  type PlacedEvent,
  type RunDetail,
  type TimelineEvent,
} from "../../lib/timeline.ts";
import styles from "./night.module.css";

// A floor, not the width. The track is measured, because a night that needs
// sideways scrolling to be seen whole is not a night anyone reads in a minute.
const MIN_TRACK_PX = 720;
// Sub-row pitch, not lane height. A lane packs as deep as its overlaps demand —
// the critic lane reaches fifteen rows on a real night — so a comfortable row
// height turns an eight-hour night into eight screens of scrolling, and the
// whole claim of this view is that a night reads in a minute.
const ROW_PX = 10;
const BAR_PX = 7;
const MIN_LANE_PX = 18;
const GUTTER_PX = 90;
const LABEL_PX = 152;
const RATES = [20, 60, 240];

export default function NightPage() {
  const [run, setRun] = useState<RunDetail | null>(null);
  const [events, setEvents] = useState<TimelineEvent[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [playheadMs, setPlayheadMs] = useState<number | null>(null);
  const [selected, setSelected] = useState<TimelineEvent | null>(null);
  const [playing, setPlaying] = useState(false);
  const [rate, setRate] = useState(RATES[0]);
  const [reducedMotion, setReducedMotion] = useState(false);
  const [trackPx, setTrackPx] = useState(MIN_TRACK_PX);
  const scroller = useRef<HTMLDivElement>(null);

  // Measured rather than assumed: a fixed track is either cut off on a laptop
  // or leaves half the window empty on a monitor, and the packing arithmetic
  // needs a real number of pixels to place bars against.
  useEffect(() => {
    const element = scroller.current;
    if (!element) return;
    const measure = () => {
      const available = element.clientWidth - LABEL_PX - GUTTER_PX - 2;
      setTrackPx(Math.max(MIN_TRACK_PX, available));
    };
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  // Read once and then followed: someone can turn the preference on while the
  // page is open, and playback that keeps running afterward ignores the setting.
  useEffect(() => {
    const query = window.matchMedia("(prefers-reduced-motion: reduce)");
    const apply = () => {
      setReducedMotion(query.matches);
      if (query.matches) setPlaying(false);
    };
    apply();
    query.addEventListener("change", apply);
    return () => query.removeEventListener("change", apply);
  }, []);

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

  // Anchored to a monotonic clock at each start, so a throttled or dropped frame
  // costs smoothness rather than accuracy. The anchor is re-taken on every state
  // change that could move the playhead independently, which is what makes
  // scrubbing mid-playback pick up from where it was dropped.
  useEffect(() => {
    if (!playing || !extent || playheadMs == null) return;
    const anchor = { wall_ms: performance.now(), playhead_ms: playheadMs, rate };
    let frame = 0;

    const tick = () => {
      const next = positionAt(anchor, performance.now(), extent);
      setPlayheadMs(next);
      if (atEnd(next, extent)) setPlaying(false);
      else frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
    // playheadMs is deliberately absent: including it restarts the anchor every
    // frame, which is the frame-accumulating behavior this exists to avoid.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [playing, rate, extent]);


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
      const placed = packLane(byLane.get(lane.lane) ?? [], extent, trackPx);
      return { lane, placed, rows: rowCount(placed) };
    });
  }, [run, events, extent, trackPx]);

  const gutter = useMemo(
    () => (run && extent ? captureExtent(run.captures, extent.start_ms) : null),
    [run, extent],
  );

  // The run's own furthest_stage is not written until it finishes, so a night
  // still in flight reports none while a stage is visibly running. The stages
  // themselves are the honest answer.
  const reachedStage = useMemo(() => {
    if (run?.furthest_stage) return run.furthest_stage;
    const started = (run?.stages ?? []).filter((s) => s.started_at_ms != null);
    if (started.length === 0) return "no stage";
    const last = started.reduce((a, b) => (b.seq > a.seq ? b : a));
    return last.status === "running" ? `${last.stage} (running)` : last.stage;
  }, [run]);

  const atPlayhead = useMemo(
    () => (playheadMs == null ? [] : eventsAt(events, playheadMs)),
    [events, playheadMs],
  );

  const onScrub = useCallback((value: number) => {
    setPlaying(false);
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

  const pxPerMs = scaleFor(extent, trackPx);
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
          <span className={styles.fact}>{reachedStage}</span>
          <span className={styles.fact}>{events.length} events</span>
          <span className={styles.fact}>
            {run.spend.total_tokens.toLocaleString()} tokens · ${run.spend.spend_usd.toFixed(4)}
          </span>
          {(run.is_synthetic || run.spend.generated) && (
            <span className={`${styles.fact} ${styles.synthetic}`}>generated</span>
          )}
        </div>
      </header>

      <div className={styles.scroller} ref={scroller}>
        <div
          className={styles.grid}
          style={{ width: `${LABEL_PX + GUTTER_PX + trackPx}px`, "--gutter-w": `${GUTTER_PX}px` } as React.CSSProperties}
        >
          {/* Drawn over every lane rather than inside the axis: a playhead you
              cannot see against the work is not a playhead. It stops at the
              gutter boundary because the evening is not part of the run. */}
          {playheadMs != null && (
            <div
              className={styles.playhead}
              style={{ left: LABEL_PX + GUTTER_PX + playheadX }}
              aria-hidden="true"
            />
          )}
          <div className={styles.rowLabel}>
            <span>evening<em>captured</em></span>
          </div>
          <div className={styles.gutter}>
            {gutter &&
              run.captures
                .filter((c) => c.created_at_ms < extent.start_ms)
                .map((capture) => (
                  <div
                    key={capture.id}
                    className={styles.capture}
                    style={{
                      left:
                        ((capture.created_at_ms - gutter.start_ms) /
                          Math.max(1, gutter.end_ms - gutter.start_ms)) *
                        (GUTTER_PX - 8),
                    }}
                    title={`${capture.title ?? "untitled"} · captured ${wallClock(capture.created_at_ms, tz)}`}
                  />
                ))}
          </div>
          <div className={styles.stages}>
            {boundStages(run.stages, extent).map(({ stage, span, open }) => (
              <div
                key={`${stage.stage}-${stage.seq}`}
                className={styles.stage}
                data-open={open}
                style={{
                  left: at(span.start_ms),
                  width: Math.max(2, (span.end_ms - span.start_ms) * pxPerMs),
                }}
                title={`${stage.stage} · ${stage.status}`}
              >
                {stage.stage}
              </div>
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
              selectedId={selected?.id ?? null}
              onSelect={setSelected}
            />
          ))}

          <div className={styles.rowLabel} />
          <div className={styles.gutterCell} />
          <div className={styles.axis}>
            {axisTicks(extent).map((ts, i, all) => (
              <span
                key={ts}
                className={styles.axisTick}
                // The outermost labels are pinned rather than centered: centered
                // on the axis ends, half of each sits outside the track and the
                // last hour of the night reads as missing.
                style={{
                  left: at(ts),
                  transform:
                    i === 0 ? "none" : i === all.length - 1 ? "translateX(-100%)" : "translateX(-50%)",
                }}
              >
                {wallClock(ts, tz)}
              </span>
            ))}
          </div>
        </div>
      </div>

      <div className={styles.scrubRow}>
        {/* Automatic playback is withheld under a reduced-motion preference —
            an hour of a night replaying itself is exactly the moving content
            the setting asks not to be shown. Scrubbing stays, because it moves
            only when someone moves it. */}
        {!reducedMotion && (
          <>
            <button
              type="button"
              className={styles.transport}
              onClick={() => {
                if (playheadMs != null && atEnd(playheadMs, extent)) setPlayheadMs(extent.start_ms);
                setPlaying((was) => !was);
              }}
              aria-pressed={playing}
            >
              {playing ? "Pause" : "Play"}
            </button>
            <label className={styles.visuallyHidden} htmlFor="rate">Playback speed</label>
            <select
              id="rate"
              className={styles.transport}
              value={rate}
              onChange={(e) => setRate(Number(e.target.value))}
            >
              {RATES.map((r) => (
                <option key={r} value={r}>{r}x</option>
              ))}
            </select>
          </>
        )}
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

// Memoized because the playhead moves sixty times a second and the lanes do
// not. Without this, every step of playback rebuilds all 1223 marks — measured
// at 5.4ms a frame against a 16.7ms budget, a third of the frame spent redrawing
// what did not change.
const Lane = memo(function Lane({
  name,
  role,
  invocations,
  placed,
  rows,
  tz,
  selectedId,
  onSelect,
}: {
  name: string;
  role: string | null;
  invocations: number;
  placed: PlacedEvent[];
  rows: number;
  tz: number;
  selectedId: number | null;
  onSelect: (event: TimelineEvent) => void;
}) {
  const height = Math.max(MIN_LANE_PX, rows * ROW_PX);
  return (
    <>
      <div className={styles.rowLabel} style={{ height }}>
        <span>
          {name}
          {role && <em>{invocations}</em>}
        </span>
      </div>
      <div className={styles.gutterCell} style={{ height }} />
      <div className={styles.track} style={{ height }}>
        {placed.map((p) => (
          <button
            key={p.event.id}
            type="button"
            className={styles.mark}
            data-severity={p.event.severity}
            data-bar={p.isBar}
            data-selected={selectedId === p.event.id}
            style={{
              left: p.x,
              width: p.width,
              top: p.row * ROW_PX + (height - rows * ROW_PX) / 2 + (ROW_PX - BAR_PX) / 2,
              height: BAR_PX,
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
});

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
