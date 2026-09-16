"use client";

// The night view.
//
// One exported page, not a `/night/[runId]` segment. `next.config.mjs` sets
// `output: "export"` so the API can serve the PWA as files — a second running
// server on the Spark is a second thing that can be down at 2am — and a dynamic
// segment would need `generateStaticParams` over run ids that are ULIDs unknown
// at build time. The run is chosen on the client instead.

import { useCallback, useEffect, useState } from "react";

import { Scrubber } from "@/components/scrubber/Scrubber";
import type { RunSummary, Timeline } from "@/lib/timeline";
import { Nav } from "@/components/shell/Shell";
import styles from "./night.module.css";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "";

type Status = "loading" | "ready" | "empty" | "unreachable";

export default function NightPage() {
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [timeline, setTimeline] = useState<Timeline | null>(null);
  const [status, setStatus] = useState<Status>("loading");

  useEffect(() => {
    const controller = new AbortController();
    fetch(`${API_BASE}/runs`, { signal: controller.signal })
      .then((r) => (r.ok ? r.json() : null))
      .then((body: RunSummary[] | null) => {
        if (!body) {
          setStatus("unreachable");
          return;
        }
        setRuns(body);
        // Newest first, from the API. A night with no events has nothing to
        // scrub, so the first one that recorded any is the useful default.
        const first = body.find((r) => r.event_count > 0) ?? body[0];
        setSelected(first?.id ?? null);
        setStatus(first ? "loading" : "empty");
      })
      .catch(() => setStatus("unreachable"));
    return () => controller.abort();
  }, []);

  useEffect(() => {
    if (selected === null) return;
    const controller = new AbortController();
    setTimeline(null);
    fetch(`${API_BASE}/runs/${selected}/timeline`, { signal: controller.signal })
      .then((r) => (r.ok ? r.json() : null))
      .then((body: Timeline | null) => {
        if (!body) {
          setStatus("unreachable");
          return;
        }
        setTimeline(body);
        setStatus("ready");
      })
      .catch(() => {
        /* Aborted by a newer selection, or the API went away. */
      });
    return () => controller.abort();
  }, [selected]);

  const pick = useCallback((id: string) => setSelected(id), []);

  return (
    <>
    <Nav />
    <main className={styles.page}>
      {runs.length > 1 ? (
        <nav className={styles.runs} aria-label="Recorded nights">
          {runs.map((run) => (
            <button
              key={run.id}
              type="button"
              className={styles.run}
              data-selected={run.id === selected}
              onClick={() => pick(run.id)}
            >
              {run.night_of}
              {run.is_synthetic ? <span className={styles.tag}>synthetic</span> : null}
            </button>
          ))}
        </nav>
      ) : null}

      {status === "unreachable" ? (
        <p className={styles.notice}>
          The orchestrator is not answering. Nothing was lost — this view only
          reads.
        </p>
      ) : null}
      {status === "empty" ? (
        <p className={styles.notice}>No night has been recorded yet.</p>
      ) : null}
      {timeline ? <Scrubber timeline={timeline} /> : null}
      {status === "loading" && !timeline ? (
        <p className={styles.notice}>Reading the night…</p>
      ) : null}
    </main>
    </>
  );
}
