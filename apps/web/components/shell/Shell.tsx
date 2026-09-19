"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { isDemoProfile } from "@/lib/profile";
import { SURFACES } from "@/lib/surfaces";
import styles from "./shell.module.css";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "";

/**
 * Whether this deployment is the judge instance, read from the served
 * capability report.
 *
 * Fetched by the shell rather than passed in by each surface. The night
 * surface shipped without the label for exactly that reason — it rendered the
 * nav and nobody remembered the prop, so the one screen a judge is most likely
 * to open was the one not saying it was a demo. A label every caller has to
 * remember is a label that goes missing.
 */
function useDemoProfile(): boolean {
  const [demo, setDemo] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    void (async () => {
      try {
        const response = await fetch(`${API_BASE}/capabilities`, {
          signal: controller.signal,
        });
        if (!response.ok) return;
        const report = (await response.json()) as { profile?: string };
        setDemo(isDemoProfile(report.profile));
      } catch {
        /* Unreachable API: no label rather than a wrong one. */
      }
    })();
    return () => controller.abort();
  }, []);
  return demo;
}

function links(pathname: string, className: string) {
  return SURFACES.map((s) => (
    <Link
      key={s.href}
      href={s.href}
      className={className}
      aria-current={pathname === s.href ? "page" : undefined}
    >
      {s.label}
    </Link>
  ));
}

/**
 * The desktop shell: a nav across the top.
 *
 * Deliberately not used on capture. The measurement is in
 * `shell.module.css` — a nav bar there costs the privacy choice its place
 * above the fold when a keyboard is open.
 */
export function Nav() {
  const pathname = usePathname();
  const demo = useDemoProfile();
  return (
    <nav className={styles.nav} aria-label="Surfaces">
      {links(pathname, styles.link)}
      <span className={styles.spacer} />
      {demo ? <DemoLabel /> : null}
    </nav>
  );
}

/**
 * Capture's shell: links after the content, never before it.
 *
 * A judge who scrolls one screen finds every surface; a person capturing at 3am
 * never sees it, which is the point.
 */
export function Footer() {
  const pathname = usePathname();
  const demo = useDemoProfile();
  return (
    <footer className={styles.footer}>
      {links(pathname, styles.link)}
      <span className={styles.spacer} />
      {demo ? <DemoLabel /> : null}
    </footer>
  );
}

/**
 * What this is, for somebody who has never seen it.
 *
 * Shown only where the served report resolves `cloud` — the judge deployment.
 * A stranger who opens the root otherwise meets a textarea reading "What's the
 * idea?" and a Capture button, which is the right screen for the person it was
 * built for and tells a visitor nothing: not that it works overnight, not that
 * it produces artifacts, not that it interviews you.
 *
 * Driven by the same fetch as the demo label rather than a build flag, because
 * `NEXT_PUBLIC_DEMO=1` would mean two builds and principle 5 says one codebase
 * separated only by compute profile.
 *
 * **Below the capture control, never above it.** `frontend` measured what
 * chrome above the input costs: at a keyboard-up 390x350 viewport a nav bar
 * takes the `local-only` option from 79% visible to 0%, and the default is the
 * policy that sends the idea off the machine. A judge scrolls one screen; the
 * person capturing at 3am never sees this.
 */
export function Explainer() {
  const demo = useDemoProfile();
  if (!demo) return null;
  return (
    <section className={styles.explainer} aria-label="What this is">
      <h2 className={styles.explainerTitle}>What this is</h2>
      <p className={styles.explainerLead}>
        An always-on assistant that turns half-formed ideas into artifacts
        overnight, then interviews you in the morning about what it got stuck
        on.
      </p>
      <ol className={styles.explainerSteps}>
        <li>
          <strong>You capture an idea</strong> in one line, choosing whether it
          may leave the machine. That is the screen above.
        </li>
        <li>
          <strong>Overnight it works</strong> — briefs, researches, mocks up,
          builds, critiques and distills, committing each stage as it finishes
          so a late failure never retracts an early success.
        </li>
        <li>
          <strong>In the morning it interviews you</strong> about what it could
          not decide alone, one question at a time.
        </li>
      </ol>
      <p className={styles.explainerNote}>
        This deployment holds no real data. Every row in it was generated from a
        fixed seed, so <strong>Morning</strong> and <strong>Night</strong> below
        show the same recorded night every time — which is what makes a
        screenshot of it reproducible.
      </p>
    </section>
  );
}

/**
 * Principle 5: the judge instance contains zero real data and must be labeled
 * in-UI as a demo. Rendered from the served capability report, so the judge
 * deployment is a caller of this code rather than a fork of it.
 *
 * Not exported: `Nav` and `Footer` are the only callers, and a symbol nothing
 * imports is surface with no consumer.
 */
function DemoLabel() {
  return (
    <span className={styles.demo} role="status">
      demo
    </span>
  );
}
