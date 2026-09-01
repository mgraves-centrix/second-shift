"use client";

// What the night view shows when it fails.
//
// It exists because the view failed on a phone and showed nothing at all — a
// white screen says the page is broken without saying what broke, and there is
// no console to open on someone else's device. Anything that reaches here is
// already unexpected, so it reports the actual message rather than a reassuring
// sentence, and offers the one action that fixes most of them.

import { useEffect } from "react";

export default function NightError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // Also on the console, for the case where someone does have one attached.
    console.error("night view failed", error);
  }, [error]);

  return (
    <main style={{ padding: "1.5rem", maxWidth: "34rem", margin: "0 auto" }}>
      <h1 style={{ fontSize: "1.05rem", margin: 0 }}>The night view failed to load.</h1>
      <p style={{ color: "#8b96a5", fontSize: "0.9rem" }}>
        This is the view failing, not the night. Nothing that was recorded has been lost.
      </p>
      <pre
        style={{
          whiteSpace: "pre-wrap",
          wordBreak: "break-word",
          background: "#14181d",
          border: "1px solid #232a32",
          borderRadius: "0.5rem",
          padding: "0.75rem",
          fontSize: "0.8rem",
        }}
      >
        {error.message}
        {error.digest ? `\n\ndigest ${error.digest}` : ""}
      </pre>
      <button type="button" onClick={reset} style={{ marginTop: "1rem" }}>
        Try again
      </button>
    </main>
  );
}
