// Measure the three rendering approaches against one real generated night.
//
//   python .../export_night.py --db <db> --out night.json
//   node measure.mjs --data night.json
//
// Playwright is imported by name. Where it is installed globally rather than
// beside this script, point PLAYWRIGHT_MODULE at its entry point — an absolute
// path is somebody's machine and does not belong in a public repository.
//
// Reports the cost of the render function itself and the frame period actually
// achieved. The first is what an approach costs; the second is what a viewer
// feels, and they diverge — a renderer can be cheap in script and still miss
// frames because the browser has style, layout and paint left to do afterwards.

import { readFileSync } from "node:fs";
import { pathToFileURL } from "node:url";

const { chromium } = await import(process.env.PLAYWRIGHT_MODULE ?? "playwright");

const args = new Map();
for (let i = 2; i < process.argv.length; i += 2) {
  args.set(process.argv[i].replace(/^--/, ""), process.argv[i + 1]);
}
const dataPath = args.get("data");
const frames = Number(args.get("frames") ?? 600);
const harness = new URL("harness.html", import.meta.url);

function stats(values) {
  const sorted = [...values].sort((a, b) => a - b);
  const at = (q) => sorted[Math.min(sorted.length - 1, Math.floor(sorted.length * q))];
  return { p50: at(0.5), p95: at(0.95), max: sorted[sorted.length - 1] };
}

const round = (n) => Math.round(n * 100) / 100;

// The pre-installed browser, where the environment names one. Playwright's own
// resolution is used otherwise.
const browser = await chromium.launch(
  process.env.PLAYWRIGHT_CHROMIUM ? { executablePath: process.env.PLAYWRIGHT_CHROMIUM } : {},
);
const page = await browser.newPage({ viewport: { width: 1400, height: 400 } });
await page.goto(pathToFileURL(harness.pathname).href);

const data = JSON.parse(readFileSync(dataPath, "utf8"));
const scale = Number(args.get("scale") ?? 1);
const loaded = await page.evaluate(([d, s]) => window.__load(d, s), [data, scale]);
console.log(
  `${loaded.events} events across ${loaded.lanes} lanes` +
    `${scale > 1 ? ` (${scale}x stress)` : ""}, ${frames} frames at 20x\n`,
);

const rows = [];
for (const mode of ["dom-incremental", "dom-naive", "canvas"]) {
  // Each mode runs twice; the first pass is discarded so a cold layout or a
  // just-in-time compile is not reported as the approach's cost.
  await page.evaluate(([m, f]) => window.__measure(m, f), [mode, 60]);
  const result = await page.evaluate(([m, f]) => window.__measure(m, f), [mode, frames]);
  // The first frames pay for the initial layout of freshly created nodes, which
  // is a real cost but a one-time one. Reported separately rather than folded
  // into `max`, where it would look like a stall that recurs.
  const settle = 5;
  const first = Math.max(...result.costs.slice(0, settle));
  const cost = stats(result.costs.slice(settle));
  const period = stats(result.periods.slice(settle));
  const fps = 1000 / period.p50;
  rows.push({ mode, cost, period, fps, first });
  console.log(
    `${mode.padEnd(16)} steady p50 ${round(cost.p50)}ms  p95 ${round(cost.p95)}ms  ` +
      `max ${round(cost.max)}ms   first ${round(first)}ms   ~${round(fps)}fps`,
  );
}

await browser.close();
console.log("\nbudget: 16.7ms per frame for 60fps");
for (const r of rows) {
  const verdict =
    r.cost.max < 16.7 ? "within budget" : "over budget on its worst steady frame";
  console.log(`  ${r.mode.padEnd(16)} ${verdict}`);
}
