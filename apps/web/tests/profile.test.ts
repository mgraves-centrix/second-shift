/**
 * The demo label, driven by served data rather than a build flag.
 *
 * Constitution principle 5: one codebase, two deployments, separated only by
 * compute profile. `NEXT_PUBLIC_DEMO=1` would mean two builds — the fork the
 * principle exists to prevent — and the judge instance would not be the same
 * artifact as the personal one.
 */
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { isDemoProfile } from "../lib/profile.ts";

test("the cloud profile is a demo deployment", () => {
  assert.equal(isDemoProfile("cloud"), true);
});

test("a local profile is not", () => {
  assert.equal(isDemoProfile("spark"), false);
  assert.equal(isDemoProfile("workstation"), false);
});

test("an absent profile is not labeled", () => {
  /** The report has not arrived yet. Labeling on absence would flash a demo
   * badge on the personal instance every time it loads. */
  assert.equal(isDemoProfile(null), false);
  assert.equal(isDemoProfile(undefined), false);
});

test("no build-time flag governs the label", () => {
  /**
   * Precise about what is forbidden. `NEXT_PUBLIC_API_BASE` is how every
   * surface reaches the API and is not a fork — an earlier version of this test
   * banned `process.env` outright and failed the moment the shell needed to
   * know where the API is, which would have pushed the label back to a prop
   * each surface has to remember.
   *
   * What must not exist is an environment variable that *decides* the label.
   */
  const shell = readFileSync(
    join(import.meta.dirname, "..", "components", "shell", "Shell.tsx"), "utf8",
  );
  assert.ok(
    !/NEXT_PUBLIC_DEMO|DEMO_MODE|IS_DEMO/i.test(shell),
    "a build-time flag decides the demo label, which is two builds",
  );
  assert.ok(
    /\/capabilities/.test(shell),
    "the label is not read from the served capability report",
  );
});

test("no surface has to remember to pass the label", () => {
  /** The night surface shipped without it for exactly this reason: it rendered
   * the nav and nobody passed the prop, so the screen a judge is most likely to
   * open was the one not saying it was a demo. */
  const shell = readFileSync(
    join(import.meta.dirname, "..", "components", "shell", "Shell.tsx"), "utf8",
  );
  assert.ok(
    !/export function (Nav|Footer)\(\s*\{[^}]*demo/.test(shell),
    "the shell takes the demo label as a prop, so a caller can forget it",
  );
});
