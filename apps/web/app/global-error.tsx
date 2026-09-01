"use client";

// The last boundary. A failure in the root layout replaces the whole document,
// so this one carries its own html and body — nothing above it survives to
// provide them.
//
// Same reason as the night view's boundary: a page that renders nothing is
// indistinguishable from a server that is down, and the two have completely
// different fixes.

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <html lang="en">
      <body
        style={{
          margin: 0,
          background: "#0b0d10",
          color: "#e6eaef",
          font: '16px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif',
          padding: "1.5rem",
        }}
      >
        <h1 style={{ fontSize: "1.05rem" }}>Second Shift failed to start.</h1>
        <pre style={{ whiteSpace: "pre-wrap", wordBreak: "break-word", fontSize: "0.8rem" }}>
          {error.message}
        </pre>
        <button type="button" onClick={reset}>
          Try again
        </button>
      </body>
    </html>
  );
}
