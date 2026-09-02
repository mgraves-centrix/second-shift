"use client";

// The night scrubber.
//
// React owns the structure; the playhead does not go through it. Marks are
// rendered once from a laid-out night and then left alone, and moving the
// playhead writes directly to the nodes it crossed. That is the shape Spike D
// measured — 0.1ms per steady frame against a 16.7ms budget, and a cost that is
// flat in night size — and a version that re-rendered on every pointer move
// would throw the measurement away.
//
// Nothing here reads a payload. Detail is fetched for the one event a person is
// looking at, never for the thousand a frame is drawn from.

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  clamp,
  eventsAt,
  formatCost,
  formatDuration,
  formatMoment,
  instantAt,
  layoutNight,
  nextPosition,
  nightProgress,
  positionOf,
  type EventDetail,
  type Night,
  type Timeline,
  type TimelineEvent,
} from "@/lib/timeline";
import styles from "./scrubber.module.css";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "";

/**
 * Lane hues, so "which agent was leading" is answerable without a legend.
 *
 * None of them is near the severity color. The first version put a warm yellow
 * here, and the distiller lane — which had no failures at all — rendered as a
 * lane of failures. A palette that can be mistaken for a severity is worse than
 * no palette: it makes the view dishonest at rest, which is the one thing it
 * must not be.
 */
const LANE_COLORS = [
  "#7ef0a8", "#7ec8f0", "#c79ef0", "#7ef0d8",
  "#f09ec8", "#9ef07e", "#a8b4c4", "#b8c47e",
];

export function Scrubber({ timeline }: { timeline: Timeline }) {
  const night = useMemo(() => layoutNight(timeline), [timeline]);
  const progress = useMemo(() => nightProgress(night), [night]);

  const plotRef = useRef<HTMLDivElement>(null);
  const headRef = useRef<HTMLDivElement>(null);
  const clockRef = useRef<HTMLDivElement>(null);
  const markRefs = useRef<(HTMLDivElement | null)[]>([]);
  // The playhead lives in a ref, not in state. It changes every frame of a drag
  // and nothing above it needs to re-render when it does.
  const positionRef = useRef(0);
  // The plot's width in pixels, kept current by a resize observer.
  //
  // The playhead moves by a pixel transform rather than a percentage one: a
  // percentage translate resolves against the element's OWN width, and the
  // playhead is one pixel wide — so `translateX(80%)` moved it 0.8px and it sat
  // at the left edge reporting the right time. Every automated check passed,
  // because they read the ARIA value. Looking at it is what caught it.
  const widthRef = useRef(0);
  const crossedRef = useRef(0);
  const announcedRef = useRef("");

  const [announced, setAnnounced] = useState("");
  // What the playhead is inside, resolved when it comes to rest rather than
  // every frame — the drag itself updates only the clock and the marks it
  // crossed, which is the whole point of rendering incrementally.
  const [atPlayhead, setAtPlayhead] = useState<TimelineEvent[]>([]);
  const [hovered, setHovered] = useState<number | null>(null);
  const [detail, setDetail] = useState<EventDetail | null>(null);

  // Detail follows the playhead, and a pointer overrides it. Without the first
  // half a keyboard user can move the playhead and never see what is under it,
  // and at roughly one event per pixel a pointer is a poor way to select one.
  const selected = hovered ?? atPlayhead[0]?.id ?? null;

  /** Move the playhead, touching only the marks it crossed. */
  const moveTo = useCallback(
    (fraction: number) => {
      const position = clamp(fraction, 0, 1);
      positionRef.current = position;
      const instant = instantAt(night, position);

      const width = widthRef.current;
      if (headRef.current) {
        headRef.current.style.transform = `translateX(${position * width}px)`;
      }

      // Forward and backward both walk the boundary rather than the whole
      // timeline: the cost is the number of marks crossed, not the number that
      // exist. A full-span drag in one frame is the worst case, and Spike D
      // measured it at 1.8ms.
      const marks = night.marks;
      let crossed = crossedRef.current;
      while (crossed < marks.length && marks[crossed].event.ts_ms <= instant) {
        markRefs.current[crossed]?.setAttribute("data-past", "true");
        crossed += 1;
      }
      while (crossed > 0 && marks[crossed - 1].event.ts_ms > instant) {
        crossed -= 1;
        markRefs.current[crossed]?.setAttribute("data-past", "false");
      }
      crossedRef.current = crossed;

      const moment = formatMoment(instant, night.timeZone);
      if (clockRef.current) {
        clockRef.current.textContent = moment;
        // Held inside the plot at the right edge, so the clock stays readable
        // when the playhead reaches the end of the night.
        const clockWidth = clockRef.current.offsetWidth;
        clockRef.current.style.transform = `translateX(${clamp(
          position * width,
          0,
          Math.max(0, width - clockWidth),
        )}px)`;
      }
      if (plotRef.current) {
        plotRef.current.setAttribute("aria-valuenow", String(Math.round(position * 1000)));
        plotRef.current.setAttribute("aria-valuetext", `${moment} ${night.timeZone}`);
      }
      // Announced at the granularity a person can follow, not once a frame.
      if (moment !== announcedRef.current) {
        announcedRef.current = moment;
        setAnnounced(moment);
      }
    },
    [night],
  );

  // The plot's width, measured rather than assumed, and kept current.
  useEffect(() => {
    const plot = plotRef.current;
    if (!plot) return;
    const measure = () => {
      widthRef.current = plot.getBoundingClientRect().width;
      moveTo(positionRef.current);
    };
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(plot);
    return () => observer.disconnect();
  }, [moveTo]);

  /** Resolve what the playhead rests inside. Called when it stops moving. */
  const settle = useCallback(() => {
    setAtPlayhead(eventsAt(night, instantAt(night, positionRef.current)));
  }, [night]);

  // Lay the playhead on the start of a freshly loaded night.
  useEffect(() => {
    crossedRef.current = 0;
    markRefs.current.forEach((node) => node?.setAttribute("data-past", "false"));
    moveTo(0);
    settle();
  }, [moveTo, settle]);

  const fromClientX = useCallback((clientX: number) => {
    const plot = plotRef.current;
    if (!plot) return 0;
    const box = plot.getBoundingClientRect();
    widthRef.current = box.width;
    return box.width > 0 ? (clientX - box.left) / box.width : 0;
  }, []);

  const onPointerDown = useCallback(
    (event: React.PointerEvent<HTMLDivElement>) => {
      event.currentTarget.setPointerCapture(event.pointerId);
      // A press on the rail is a scrub, so the pointer stops naming one mark.
      setHovered(null);
      moveTo(fromClientX(event.clientX));
    },
    [fromClientX, moveTo],
  );

  const onPointerMove = useCallback(
    (event: React.PointerEvent<HTMLDivElement>) => {
      if (event.buttons === 0) return;
      moveTo(fromClientX(event.clientX));
    },
    [fromClientX, moveTo],
  );

  const onKeyDown = useCallback(
    (event: React.KeyboardEvent<HTMLDivElement>) => {
      const next = nextPosition(positionRef.current, event.key, event.shiftKey);
      if (next === null) return;
      event.preventDefault();
      setHovered(null);
      moveTo(next);
    },
    [moveTo],
  );

  // Detail for the one event being looked at. Aborted on change, so a fast
  // sweep across the timeline cannot land an earlier answer over a later one.
  useEffect(() => {
    if (selected === null) {
      setDetail(null);
      return;
    }
    const controller = new AbortController();
    fetch(`${API_BASE}/events/${selected}`, { signal: controller.signal })
      .then((r) => (r.ok ? r.json() : null))
      .then((body: EventDetail | null) => body && setDetail(body))
      .catch(() => {
        /* Aborted, or the API is unreachable. The timeline still scrubs. */
      });
    return () => controller.abort();
  }, [selected]);

  const laneColor = (index: number) => LANE_COLORS[index % LANE_COLORS.length];
  const current = detail ?? null;

  return (
    <section className={styles.night} aria-label="Night timeline">
      <header className={styles.head}>
        <h1 className={styles.title}>Night of {night.run.night_of}</h1>
        <span className={styles.sub}>
          {night.run.event_count} events · {night.lanes.length} lanes ·{" "}
          {formatDuration(night.span)} · {night.timeZone}
        </span>
        {night.run.is_synthetic ? (
          <span className={styles.badge} data-synthetic="true">
            synthetic
          </span>
        ) : null}
        {/* Read from the stages: `run.outcome` is null on every recorded run,
            and a night that stopped part-way says so here or nowhere. */}
        <span
          className={styles.badge}
          data-outcome={progress.finished ? "complete" : "degraded"}
        >
          {progress.finished
            ? `all ${progress.total} stages complete`
            : `${progress.complete} of ${progress.total} stages · ${progress.unfinished
                .map((s) => `${s.stage} ${s.status}`)
                .join(", ")}`}
        </span>
      </header>

      <div className={styles.frame}>
        <div className={styles.rail} aria-hidden="true">
          {night.lanes.map((lane, index) => (
            <div
              key={lane}
              className={styles.laneName}
              style={{ color: laneColor(index) }}
            >
              {lane}
            </div>
          ))}
        </div>

        <div
          ref={plotRef}
          className={styles.plot}
          role="slider"
          tabIndex={0}
          aria-label={`Playback position through the night of ${night.run.night_of}`}
          aria-valuemin={0}
          aria-valuemax={1000}
          aria-valuenow={0}
          aria-valuetext={`${formatMoment(night.from, night.timeZone)} ${night.timeZone}`}
          onPointerDown={onPointerDown}
          onPointerMove={onPointerMove}
          onPointerUp={settle}
          onKeyDown={onKeyDown}
          onKeyUp={settle}
        >
          <div ref={clockRef} className={styles.clock} />
          {night.lanes.map((lane, laneIndex) => (
            <div key={lane} className={styles.lane}>
              {night.marks.map((mark, markIndex) =>
                mark.lane !== laneIndex ? null : (
                  <div
                    key={mark.event.id}
                    ref={(node) => {
                      markRefs.current[markIndex] = node;
                    }}
                    className={styles.mark}
                    data-tick={!mark.bar}
                    data-severe={mark.severe}
                    data-depth={mark.depth}
                    data-past="false"
                    data-selected={selected === mark.event.id}
                    style={{
                      left: `${mark.x * 100}%`,
                      width: mark.bar ? `${mark.w * 100}%` : undefined,
                      ["--lane-color" as string]: laneColor(laneIndex),
                    }}
                    onPointerEnter={() => setHovered(mark.event.id)}
                    title={`${mark.event.label}${
                      mark.event.duration_ms === null
                        ? ""
                        : ` · ${formatDuration(mark.event.duration_ms)}`
                    }`}
                  />
                ),
              )}
            </div>
          ))}
          <div ref={headRef} className={styles.playhead} />
        </div>
      </div>

      <p className={styles.legend}>
        <span>
          <i className={styles.swatchBar} /> a duration
        </span>
        <span>
          <i className={styles.swatchTick} /> an instant
        </span>
        <span>
          <i className={styles.swatchSevere} /> a failure
        </span>
      </p>

      <p className={styles.atPlayhead}>
        {atPlayhead.length === 0
          ? "nothing in progress at the playhead"
          : `${atPlayhead.length} in progress: ${atPlayhead
              .slice(0, 3)
              .map((e) => `${e.lane} — ${e.label}`)
              .join("; ")}${atPlayhead.length > 3 ? ` and ${atPlayhead.length - 3} more` : ""}`}
      </p>

      <div className={styles.detail}>
        {current === null ? (
          <p className={styles.empty}>
            Drag or use the arrow keys to scrub. Point at an event for the model
            calls its invocation made.
          </p>
        ) : (
          <>
            <div className={styles.detailHead}>
              <span className={styles.detailLabel}>{current.label}</span>
              <span className={styles.detailMeta}>
                {current.lane} · {current.kind} ·{" "}
                {formatMoment(current.ts_ms, night.timeZone)}
                {current.duration_ms === null
                  ? ""
                  : ` · ${formatDuration(current.duration_ms)}`}
              </span>
            </div>
            {current.model_calls.length === 0 ? (
              <p className={styles.empty}>
                No model call was made by this invocation.
              </p>
            ) : (
              <>
                {/* Named for what it is. An event carries no model call id, so
                    these are the calls the invocation made, not the call behind
                    this event. */}
                <p className={styles.detailMeta}>
                  model calls in this invocation
                </p>
                <ul className={styles.calls}>
                  {current.model_calls.map((call) => (
                    <li key={call.id} className={styles.call}>
                      <strong>{call.model}</strong>
                      <span>{call.provider}</span>
                      <span>{call.policy}</span>
                      <span>{call.total_tokens.toLocaleString()} tokens</span>
                      <span>{formatCost(call.estimated_cost_usd)}</span>
                      {call.latency_ms === null ? null : (
                        <span>{formatDuration(call.latency_ms)}</span>
                      )}
                    </li>
                  ))}
                </ul>
              </>
            )}
          </>
        )}
      </div>

      <div className={styles.visuallyHidden} role="status" aria-live="polite">
        {announced}
      </div>
    </section>
  );
}

/** Events in progress at the playhead. Exported for the page's summary line. */
export { eventsAt, positionOf };
export type { Night };
