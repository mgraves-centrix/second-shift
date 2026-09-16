"use client";

import { useCallback, useEffect, useState } from "react";
import { newUlid } from "@/lib/ulid";
import { drain, enqueue, pendingCount, type PendingEntry } from "@/lib/queue";
import { Footer } from "@/components/shell/Shell";
import styles from "./capture.module.css";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "";

interface PolicyAvailability {
  policy: string;
  available: boolean;
  reason: string | null;
}

interface Capabilities {
  profile: string;
  degraded: boolean;
  policies: PolicyAvailability[];
}

export default function Capture() {
  const [text, setText] = useState("");
  const [capabilities, setCapabilities] = useState<Capabilities | null>(null);
  const [policy, setPolicy] = useState("cloud-assisted");
  const [waiting, setWaiting] = useState(0);
  const [status, setStatus] = useState<{ message: string; kind: "ok" | "warn" } | null>(null);
  const [busy, setBusy] = useState(false);

  const refreshCount = useCallback(async () => {
    try {
      setWaiting(await pendingCount());
    } catch {
      /* IndexedDB unavailable; the count is a convenience, not the record */
    }
  }, []);

  useEffect(() => {
    void refreshCount();
    // The capability report is fetched, never assumed. An unavailable policy is
    // rendered disabled with its reason rather than hidden, so the privacy model
    // is legible at the moment it applies.
    fetch(`${API_BASE}/capabilities`)
      .then((r) => (r.ok ? r.json() : null))
      .then((c: Capabilities | null) => c && setCapabilities(c))
      .catch(() => setCapabilities(null));
  }, [refreshCount]);

  const sync = useCallback(async () => {
    const result = await drain(API_BASE);
    await refreshCount();
    if (result.sent > 0) {
      setStatus({ message: `synced ${result.sent}`, kind: "ok" });
    }
  }, [refreshCount]);

  useEffect(() => {
    void sync();
    window.addEventListener("online", sync);
    return () => window.removeEventListener("online", sync);
  }, [sync]);

  useEffect(() => {
    if ("serviceWorker" in navigator) {
      navigator.serviceWorker.register("/sw.js").catch(() => {
        // No service worker means no offline shell. Capture online still works.
      });
    }
  }, []);

  async function capture(event: React.FormEvent) {
    event.preventDefault();
    const body = text.trim();
    if (!body || busy) return;
    setBusy(true);

    // Identity and time are fixed here, before any network attempt, so the
    // record is complete whether it is sent now or drained in three days.
    const createdAt = Date.now();
    const entry: PendingEntry = {
      id: newUlid(createdAt),
      created_at_ms: createdAt,
      captured_tz: Intl.DateTimeFormat().resolvedOptions().timeZone,
      tz_offset_min: -new Date(createdAt).getTimezoneOffset(),
      policy,
      text: body,
      modality: "text",
      capture_profile: capabilities?.profile ?? null,
    };

    try {
      await enqueue(entry);
      setText("");
      await refreshCount();
      const result = await drain(API_BASE);
      setStatus(
        result.remaining > 0
          ? { message: "captured — waiting to sync", kind: "warn" }
          : { message: "captured", kind: "ok" },
      );
      await refreshCount();
    } catch {
      setStatus({ message: "could not save locally — try again", kind: "warn" });
    } finally {
      setBusy(false);
    }
  }

  const policies = capabilities?.policies ?? [
    { policy: "cloud-assisted", available: true, reason: null },
    { policy: "local-only", available: true, reason: null },
  ];

  return (
    <main className={styles.page}>
      <div className={styles.bar}>
        <h1>Second Shift</h1>
        {/* A count, deliberately. There is no per-item surface for a retry or
            delete control to attach to — that is the scope boundary, enforced
            by what does not exist. */}
        <span className={styles.pending} data-zero={waiting === 0}>
          {waiting === 0 ? "all synced" : `${waiting} waiting to sync`}
        </span>
      </div>

      <form onSubmit={capture}>
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="What's the idea?"
          autoFocus
          aria-label="Idea"
        />

        <fieldset>
          <legend>Privacy</legend>
          {policies.map((p) => (
            <label key={p.policy} className={styles.policy} data-available={p.available}>
              <input
                type="radio"
                name="policy"
                value={p.policy}
                checked={policy === p.policy}
                disabled={!p.available}
                onChange={() => setPolicy(p.policy)}
              />
              <span>
                <span className={styles.policyName}>{p.policy}</span>
                {!p.available && p.reason ? (
                  <span className={styles.policyReason}>unavailable — {p.reason}</span>
                ) : null}
              </span>
            </label>
          ))}
        </fieldset>

        <button type="submit" disabled={busy || text.trim().length === 0}>
          {busy ? "capturing…" : "Capture"}
        </button>
      </form>

      <div className={styles.status} data-kind={status?.kind ?? "ok"} role="status">
        {status?.message ?? ""}
      </div>

      <Footer />
    </main>
  );
}
