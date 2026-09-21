/**
 * The night view, in a real browser, against a real orchestrator.
 *
 * Rendering is asserted from geometry — where the playhead actually is on the
 * page — never from ARIA. On 2 Sep the playhead moved by a percentage transform
 * of its own one-pixel width, so it sat still while three tests passed, because
 * each of them read `aria-valuenow`, which was correct.
 */
import assert from "node:assert/strict";
import { after, before, test } from "node:test";

import type { Browser, Page } from "playwright-core";

import { launchBrowser, startOrchestrator, type Orchestrator } from "./support.ts";

let orchestrator: Orchestrator;
let browser: Browser;
let page: Page;

before(async () => {
  orchestrator = await startOrchestrator();
  browser = await launchBrowser();
  page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
  await page.goto(`${orchestrator.url}/night/`);
  await page.getByRole("slider").waitFor({ timeout: 15_000 });
});

after(async () => {
  await browser?.close();
  await orchestrator?.stop();
});

/** Where the playhead is drawn, as a fraction of the plot's width. */
async function drawnPosition(): Promise<number> {
  return page.evaluate(() => {
    const plot = document.querySelector('[role="slider"]')!.getBoundingClientRect();
    const head = document.querySelector("[data-playhead]")!.getBoundingClientRect();
    return (head.left - plot.left) / plot.width;
  });
}

test("a seeded night renders its lanes and every event", async () => {
  const api = await (await fetch(`${orchestrator.url}/runs`)).json();
  assert.equal(api.length, 1, "the fixture seeds exactly one night");

  const marks = await page.locator("[data-past]").count();
  assert.equal(marks, api[0].event_count, "an event recorded by the night is missing from the view");

  const lanes = await page.evaluate(
    () => document.querySelector('[role="slider"]')!.children.length - 2,
  );
  assert.ok(lanes > 1, `a night of several agent roles rendered ${lanes} lane(s)`);
});

test("the stages the night recorded are the stages the view reports", async () => {
  const [run] = await (await fetch(`${orchestrator.url}/runs`)).json();
  const timeline = await (await fetch(`${orchestrator.url}/runs/${run.id}/timeline`)).json();
  assert.ok(timeline.stages.length > 0, "the seeded night has no stages to report");

  const badge = await page.locator("[data-outcome]").textContent();
  assert.match(
    badge ?? "",
    new RegExp(`\\b${timeline.stages.length}\\b`),
    `the stage summary "${badge}" does not account for the ${timeline.stages.length} recorded stages`,
  );
});

test("the playhead is drawn where the keyboard puts it", async () => {
  const slider = page.getByRole("slider");
  await slider.focus();

  await page.keyboard.press("Home");
  assert.ok(Math.abs(await drawnPosition()) < 0.01, "Home did not draw the playhead at the start");

  await page.keyboard.press("End");
  const end = await drawnPosition();
  assert.ok(end > 0.98, `End drew the playhead at ${end.toFixed(3)} of the plot, not its end`);

  await page.keyboard.press("Home");
  for (let i = 0; i < 5; i += 1) await page.keyboard.press("PageUp");
  const partway = await drawnPosition();
  assert.ok(
    partway > 0.05 && partway < 0.95,
    `five coarse steps drew the playhead at ${partway.toFixed(3)} — it did not move with the value`,
  );
});

test("scrubbing to the end marks every event as passed", async () => {
  await page.getByRole("slider").focus();
  await page.keyboard.press("End");

  const unpassed = await page.locator('[data-past="false"]').count();
  assert.equal(unpassed, 0, `${unpassed} event(s) still read as ahead of a playhead at the end`);
});

test("a bar too short to see is still wider than a tick", async () => {
  const narrowest = await page.evaluate(() => {
    const plot = document.querySelector('[role="slider"]')!.getBoundingClientRect().width;
    const bars = [...document.querySelectorAll('[data-tick="false"]')];
    return Math.min(...bars.map((b) => b.getBoundingClientRect().width)) / plot;
  });
  assert.ok(
    narrowest >= 0.0024,
    `the narrowest bar is ${(narrowest * 100).toFixed(3)}% of the plot — narrower than the minimum`,
  );
});

test("scrubbing the whole night touches each mark about once, not once per frame", async () => {
  // The property Spike D measured and nothing has guarded since: the cost of a
  // frame is proportional to the marks the playhead CROSSES, not to the size of
  // the night. That is what holds 0.1ms per steady frame at 1,223 events and at
  // 9,784, and it is the reason DOM won over canvas here.
  //
  // Counted as attribute writes rather than timed in milliseconds. A wall clock
  // on a CI runner is a coin flip, and this property is not — but more than
  // that, a timing assertion would pass the exact regression this exists to
  // catch: Spike D measured the re-rendering implementation at 1.8ms on a night
  // this small, comfortably inside a 16.7ms budget. It only falls over on a
  // night eight times longer, which is the night nobody tests against.
  const slider = page.getByRole("slider");
  await slider.focus();
  await page.keyboard.press("Home");

  const marks = await page.locator("[data-past]").count();
  const steps = 40;

  await page.evaluate(() => {
    const counter = { writes: 0 };
    (window as unknown as { __scrubWrites: { writes: number } }).__scrubWrites = counter;
    new MutationObserver((records) => {
      counter.writes += records.length;
    }).observe(document.querySelector('[role="slider"]')!, {
      attributes: true,
      attributeFilter: ["data-past"],
      subtree: true,
    });
  });

  for (let i = 0; i < steps; i += 1) await page.keyboard.press("PageUp");

  const writes = await page.evaluate(
    () => (window as unknown as { __scrubWrites: { writes: number } }).__scrubWrites.writes,
  );

  assert.ok(
    writes > marks / 2,
    `only ${writes} marks were touched crossing a night of ${marks} — the playhead did ` +
      "not cross it, so this test proved nothing",
  );
  assert.ok(
    writes <= marks * 2,
    `crossing ${marks} marks in ${steps} steps wrote data-past ${writes} times. Crossing ` +
      `each once is ${marks}; re-rendering every step would be about ${marks * steps}. ` +
      "The scrubber is redrawing rather than moving.",
  );
});
