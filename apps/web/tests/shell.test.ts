/**
 * The shell's shape, and why it is asymmetric.
 *
 * The asymmetry is measured rather than stylistic: rendering the built capture
 * page at keyboard-up viewports with the shipped nav inserted showed that at
 * 390×350 a nav bar takes the `local-only` policy option from 79% visible to
 * 0%. The default is `cloud-assisted`, so a person who does not scroll takes
 * the wider policy by omission — a privacy outcome, not a layout preference.
 *
 * These tests hold the structural half of that. The visual half is a
 * screenshot, in the change's tasks.
 */
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { SURFACES } from "../lib/surfaces.ts";

const APP = join(import.meta.dirname, "..", "app");
const SHELL = join(import.meta.dirname, "..", "components", "shell");

test("capture renders its links after the capture control, never before", () => {
  const page = readFileSync(join(APP, "page.tsx"), "utf8");
  const button = page.indexOf("<button");
  const footer = page.indexOf("<Footer");
  assert.ok(button > 0 && footer > 0, "capture lost its button or its footer");
  assert.ok(
    footer > button,
    "capture's onward links moved above the capture control, which is the " +
      "vertical space the privacy choice competes for when a keyboard is open",
  );
});

test("capture does not import the nav", () => {
  const page = readFileSync(join(APP, "page.tsx"), "utf8");
  assert.ok(!/\bNav\b/.test(page), "a nav bar appeared on the 3am screen");
});

test("the desktop surface carries the nav", () => {
  const night = readFileSync(join(APP, "night", "page.tsx"), "utf8");
  assert.ok(/<Nav\b/.test(night), "the night surface lost its navigation");
});

test("every built surface is reachable from the shell", () => {
  /** Asserted against the exported list rather than the file's text, so the
   * test exercises the symbol the next session is told to extend. */
  assert.deepEqual(
    SURFACES.map((s) => s.href),
    ["/", "/morning/", "/night/"],
    "a surface is not reachable without typing a URL",
  );
});

test("every surface carries a label", () => {
  for (const surface of SURFACES) {
    assert.ok(surface.label.length > 0, `${surface.href} has no label`);
  }
});

test("surface links carry a trailing slash", () => {
  /** `next.config.mjs` sets `trailingSlash: true` and the app is a static
   * export. A link without one is a redirect the file server cannot perform. */
  for (const { href } of SURFACES) {
    assert.ok(
      href === "/" || href.endsWith("/"),
      `${href} needs a trailing slash under static export`,
    );
  }
});
