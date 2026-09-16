"use client";

// What a surface shows when it fails.
//
// A route failed on a phone and showed nothing at all — a white screen says the
// page is broken without saying what broke, and there is no console to open on
// someone else's device. Anything that reaches here is already unexpected, so it
// reports the actual message rather than a reassuring sentence, and offers the
// one action that fixes most of them.

import { useEffect } from "react";

import styles from "./route-error.module.css";

export function RouteError({
  surface,
  error,
  reset,
}: {
  /** What failed, in words: "The night view", "The morning". */
  surface: string;
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // Also on the console, for the case where someone does have one attached.
    console.error(`${surface} failed`, error);
  }, [surface, error]);

  return (
    <main className={styles.page}>
      <h1 className={styles.title}>{surface} failed to load.</h1>
      <p className={styles.note}>
        This is the view failing, not the night. Nothing that was recorded has been lost.
      </p>
      <pre className={styles.detail}>
        {error.message}
        {error.digest ? `\n\ndigest ${error.digest}` : ""}
      </pre>
      <button type="button" onClick={reset} className={styles.retry}>
        Try again
      </button>
    </main>
  );
}
