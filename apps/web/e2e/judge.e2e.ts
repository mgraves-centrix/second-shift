/**
 * The path a judge actually takes, in a real browser against a real
 * orchestrator.
 *
 * Everything else in this directory tests the scrubber, which is the component
 * a judge looks at. This tests the walk: landing, moving between surfaces,
 * answering a question, and whether the deployment says what it is. None of
 * that had been exercised outside unit tests, and the two failures it is
 * written to catch are both silent — a nav link that 404s in a static export
 * still renders, and a missing demo label looks exactly like a real instance.
 */
import assert from "node:assert/strict";
import { after, before, test } from "node:test";

import type { Browser, Page } from "playwright-core";

import {
  launchBrowser,
  startOrchestrator,
  visitHydrated,
  type Orchestrator,
} from "./support.ts";

let orchestrator: Orchestrator;
let browser: Browser;
let page: Page;

before(async () => {
  orchestrator = await startOrchestrator();
  browser = await launchBrowser();
  page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
});

after(async () => {
  await browser?.close();
  await orchestrator?.stop();
});

/** The surfaces the shell offers, read from the app rather than restated. */
const { SURFACES } = await import("../lib/surfaces.ts");

test("every surface the shell offers is reachable by clicking it", async () => {
  // A static export resolves `/morning/` and `/morning` differently, and a link
  // to the wrong one renders a shell with nothing in it rather than an error.
  // `surfaces.test.ts` asserts each entry resolves to a route on disk, which is
  // the check that passes while the click does not.
  //
  // Waited for by URL rather than by `networkidle`. The first draft of this
  // used the latter and reported that clicking Morning went to `/` — a client
  // navigation had not swapped the DOM yet, so the assertion read the page it
  // was leaving. That failure looked exactly like the broken link this test is
  // for, which is the argument for waiting on the thing being asserted.
  await visitHydrated(page, `${orchestrator.url}/`);

  for (const surface of SURFACES) {
    const link = page.getByRole("link", { name: surface.label }).first();
    await link.waitFor({ timeout: 15_000 });
    await link.click();
    try {
      await page.waitForURL(`**${surface.href}`, { timeout: 15_000 });
    } catch {
      assert.fail(
        `clicking ${surface.label} left the browser at ${new URL(page.url()).pathname} ` +
          `rather than ${surface.href}`,
      );
    }

    const body = (await page.locator("body").textContent()) ?? "";
    assert.ok(
      body.trim().length > 40,
      `${surface.href} rendered ${body.trim().length} characters — the route ` +
        "resolved to an empty shell, which is what a wrong trailing slash looks like",
    );
  }
});

test("a demo deployment says so, on every surface", async () => {
  // Principle 5: the judge instance must be labeled in-UI as a demo. The
  // shell's own comment records that the night surface once shipped without the
  // label because each caller had to remember a prop, so every surface is
  // checked rather than the first one.
  for (const surface of SURFACES) {
    await visitHydrated(page, `${orchestrator.url}${surface.href}`);
    const label = page.getByRole("status").filter({ hasText: "demo" }).first();
    await label.waitFor({ timeout: 15_000 });
    assert.ok(await label.isVisible(), `${surface.href} does not say it is a demo`);
  }
});

test("a deployment that is not the judge instance does not claim to be a demo", async () => {
  // The other direction, and the one that makes the test above mean something:
  // a label hardcoded to always render would pass that test and would mark the
  // personal instance a demo. Served from a second orchestrator on a local
  // profile, against the same build — principle 5 says one codebase separated
  // only by compute profile, so this is the separation working.
  const personal = await startOrchestrator(42, "spark");
  try {
    const other = await browser.newPage();
    try {
      // Hydrated before counting, or the absence proves only that the effect
      // had not run yet. This assertion was vacuous until the barrier existed.
      await visitHydrated(other, `${personal.url}/night/`);
      await other.getByRole("slider").waitFor({ timeout: 15_000 });
      const labels = await other.getByRole("status").filter({ hasText: "demo" }).count();
      assert.equal(labels, 0, "a local profile rendered the demo label");
    } finally {
      await other.close();
    }
  } finally {
    await personal.stop();
  }
});

test("the interview can be completed by typing", async () => {
  // Principle 4: every voice interaction has a working text equivalent that is
  // not a degraded fallback. The interview is the product, so this is the one
  // interaction that has to work with a keyboard alone.
  const morning = await (await fetch(`${orchestrator.url}/morning`)).json();
  assert.ok(morning.questions.length > 0, "the seeded night left no question to answer");
  const [first] = morning.questions;

  await visitHydrated(page, `${orchestrator.url}/morning/`);
  const box = page.locator("textarea").first();
  await box.waitFor({ timeout: 15_000 });
  await box.fill("File it under the one it is mostly about, and cross-reference.");
  const submit = page.locator("button[data-outcome]").first();
  await submit.click();

  await page.waitForFunction(
    () => document.querySelector("button[data-outcome]")?.getAttribute("data-outcome") !== "idle",
    undefined,
    { timeout: 15_000 },
  );
  const outcome = await submit.getAttribute("data-outcome");
  assert.notEqual(outcome, "error", "submitting a typed answer reported an error");

  // Recorded, not merely acknowledged. A screen that says "saved" while the
  // decision stays open is the failure this asserts past.
  const after = await (await fetch(`${orchestrator.url}/morning`)).json();
  const stillOpen = after.questions.some(
    (q: { decision_id: string }) => q.decision_id === first.decision_id,
  );
  assert.ok(!stillOpen, "the answered question is still listed as open");
});

test("a demo deployment holds no real data", async () => {
  // Principle 5 again, the half that is not about labels: the judge instance
  // must contain zero real data. Asserted from the rollups the API serves,
  // because `is_synthetic` is what the views filter on and a real row here
  // would be invisible in the UI and decisive in a measurement.
  const runs = await (await fetch(`${orchestrator.url}/runs`)).json();
  assert.ok(runs.length > 0, "nothing was seeded, so this asserts nothing");
  for (const run of runs) {
    assert.equal(
      run.is_synthetic,
      true,
      `run ${run.id} on a demo deployment is not marked synthetic`,
    );
  }
});
