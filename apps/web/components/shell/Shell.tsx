"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { isDemoProfile } from "@/lib/profile";
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

/** Every built surface, in the order a person meets them. */
export const SURFACES: ReadonlyArray<{ href: string; label: string }> = [
  { href: "/", label: "Capture" },
  { href: "/night/", label: "Night" },
];

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
 * Principle 5: the judge instance contains zero real data and must be labeled
 * in-UI as a demo. Rendered from the served capability report, so the judge
 * deployment is a caller of this code rather than a fork of it.
 */
export function DemoLabel() {
  return (
    <span className={styles.demo} role="status">
      demo
    </span>
  );
}
