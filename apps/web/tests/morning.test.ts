/**
 * The interview, and the two rules it is most likely to break.
 *
 * Principle 4 is asserted by absence: the surface references no microphone API
 * at all, which is a stronger statement than mocking a permission denial —
 * code that never asks cannot be refused. Principle 6 is asserted the same way:
 * there is no submit path that carries text without a decision id, so the
 * excluded chat interface has nowhere to grow from.
 */
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, existsSync } from "node:fs";
import { join } from "node:path";

import {
  LEAVES_THE_MACHINE,
  artifactLabel,
  nothingWaiting,
  NO_REASON_RECORDED,
  OUTCOMES,
  completedStages,
  nightSummary,
  stageReason,
  submitAnswer,
  type NightLine,
  type StageLine,
} from "../lib/morning.ts";
import { SURFACES } from "../lib/surfaces.ts";

const APP = join(import.meta.dirname, "..", "app");
const MORNING = readFileSync(join(APP, "morning", "page.tsx"), "utf8");

function stage(over: Partial<StageLine> = {}): StageLine {
  return { stage: "brief", status: "complete", reason: null, artifacts: [], ...over };
}

// -- principle 4 -----------------------------------------------------------

test("the morning surface references no speech API", () => {
  /** ADR 0006 binds an end-of-utterance detector that has never been run. A
   * waveform with no transcription behind it is decoration on the one screen
   * that is the product, and a turn that needs a microphone is a principle 4
   * violation rather than a limitation. */
  for (const api of [
    "getUserMedia",
    "MediaRecorder",
    "SpeechRecognition",
    "webkitSpeechRecognition",
    "AudioContext",
  ]) {
    assert.ok(
      !MORNING.includes(api),
      `the interview reached for ${api}; every turn must complete by typing`,
    );
  }
});

test("an answer states its modality rather than relying on a default", () => {
  /** So the column that will carry `voice` has a caller passing it today. */
  assert.match(MORNING, /modality:\s*"text"/);
});

// -- principle 6, and NOT_BUILDING's excluded chat interface ---------------

test("every submission carries a decision id", async () => {
  const calls: string[] = [];
  const original = globalThis.fetch;
  globalThis.fetch = (async (url: string | URL) => {
    calls.push(String(url));
    return new Response(
      JSON.stringify({ decision_id: "d", status: "decided", answered_at_ms: 1 }),
      { status: 200, headers: { "content-type": "application/json" } },
    );
  }) as typeof fetch;
  try {
    await submitAnswer("01JDECISION", { answer: "yes", status: "decided" });
  } finally {
    globalThis.fetch = original;
  }

  assert.equal(calls.length, 1);
  assert.ok(
    calls[0].includes("01JDECISION"),
    "an answer was submitted to a route that did not name a question",
  );
  assert.match(calls[0], /\/decisions\/[^/]+\/answer$/);
});

test("the surface posts to no route but the answer route", () => {
  const posts = MORNING.match(/fetch\(/g) ?? [];
  assert.equal(
    posts.length,
    1,
    "the interview grew a second request path; the only write is an answer " +
      "against a question, and the only read is the briefing",
  );
  assert.ok(
    !/\/(chat|message|ask|instruct)/.test(MORNING),
    "a route appeared that takes an instruction with nowhere to attach it",
  );
});

test("the four outcomes are the four decision states", () => {
  assert.deepEqual(
    OUTCOMES.map((o) => o.status),
    ["decided", "queued-for-tonight", "deferred", "obsolete"],
    "the outcome set drifted from the decisions table's CHECK constraint",
  );
});

// -- principle 3 -----------------------------------------------------------

test("a skipped stage says the reason was not recorded, not nothing", () => {
  /** `run_stages` has no reason column, so a blank would read as "no reason"
   * when the truth is "not stored". They are not the same claim. */
  assert.equal(stageReason(stage({ status: "skipped" })), NO_REASON_RECORDED);
});

test("a failed stage carries the reason from the ledger", () => {
  assert.equal(
    stageReason(stage({ status: "failed", reason: "no API key configured" })),
    "no API key configured",
  );
});

test("a complete stage needs no reason", () => {
  assert.equal(stageReason(stage()), null);
});

test("a half-failed night still reports what it produced", () => {
  const night: NightLine = {
    run_id: "r",
    entry_id: "e",
    night_of: "2026-09-02",
    outcome: "degraded",
    effective_policy: "cloud-assisted",
    stages: [
      stage({ stage: "brief", artifacts: ["brief.md"] }),
      stage({ stage: "research", status: "failed", reason: "no key" }),
      stage({ stage: "mockups", status: "skipped" }),
    ],
  };

  assert.deepEqual(
    completedStages(night).map((s) => s.stage),
    ["brief"],
  );
  assert.equal(night.stages.length, 3, "a failed stage was dropped from the record");
  assert.equal(nightSummary(night), "1 of 3 complete");
});

test("the night summary counts what completed, not what ran", () => {
  const night: NightLine = {
    run_id: "r",
    entry_id: "e",
    night_of: "2026-09-02",
    outcome: "complete",
    effective_policy: "local-only",
    stages: [stage(), stage({ stage: "research", status: "skipped" })],
  };

  assert.equal(nightSummary(night), "1 of 2 complete");
});

test("an artifact label drops the night and run already on screen", () => {
  const night: NightLine = {
    run_id: "01M1JH7JRB9RVBE94CCPRF3R3R",
    entry_id: "e",
    night_of: "2026-09-02",
    outcome: "degraded",
    effective_policy: "local-only",
    stages: [],
  };

  assert.equal(
    artifactLabel(
      "2026-09-02/01M1JH7JRB9RVBE94CCPRF3R3R/mockup/0/mockup.md",
      night,
    ),
    "mockup/0/mockup.md",
    "the run's ULID was repeated on every stage line",
  );
});

test("an artifact label keeps a path it does not recognize", () => {
  /** Never invent a location. A path shaped differently from what the store
   * writes is shown whole rather than trimmed on a guess. */
  const night: NightLine = {
    run_id: "r",
    entry_id: "e",
    night_of: "2026-09-02",
    outcome: null,
    effective_policy: "local-only",
    stages: [],
  };

  assert.equal(
    artifactLabel("/somewhere/else/brief.md", night),
    "/somewhere/else/brief.md",
  );
});

test("the outcome controls are not visually ranked", () => {
  /** An accent on one outcome reads as the recommended answer, and a person in
   * a hurry clicks the highlighted button — which biases the record away from
   * `Defer`. Deferring being first-class has to be true of the pixels. */
  const css = readFileSync(
    join(APP, "morning", "morning.module.css"),
    "utf8",
  );
  assert.ok(
    !/\.outcome\[data-outcome=/.test(css),
    "one outcome was styled differently from the other three",
  );
});

// -- principle 2 -----------------------------------------------------------

test("the egress warning says what is true, not what the field name says", () => {
  /** The server marks every question on a `local-only` entry, which over-warns:
   * deferring one sends nothing anywhere. So the sentence a person reads claims
   * an answer *can* authorize it, never that it will. */
  assert.match(LEAVES_THE_MACHINE, /local-only/);
  assert.match(LEAVES_THE_MACHINE, /can\b/);
  assert.ok(
    !/\bwill\b/.test(LEAVES_THE_MACHINE),
    "the warning promises an egress that deferring does not cause",
  );
});

test("the warning is read from the response, never re-derived", () => {
  assert.ok(
    !/local-only/.test(MORNING),
    "the screen grew its own copy of the server's rule, which is a second " +
      "thing that can disagree",
  );
  assert.match(MORNING, /will_leave_the_machine/);
});

test("an empty morning claims nothing about a night that did not run", () => {
  /** "The night got stuck on nothing it could not decide for itself" was
   * rendered on a morning with no night at all — the state you land in right
   * after answering, because acting advances the delta boundary past the run
   * you just discussed. Found by reloading the page after an interview.
   *
   * The first version of this test read the branch out of `page.tsx` and
   * matched the explanatory comment above the code rather than the code, which
   * is exactly why the logic lives in a module instead. */
  assert.ok(
    !/night/i.test(nothingWaiting(false)),
    "a morning with no night said something about the night",
  );
  assert.match(nothingWaiting(true), /night/);
  assert.notEqual(nothingWaiting(true), nothingWaiting(false));
});

// -- the interview does not fail open --------------------------------------

test("a rejected answer throws rather than resolving", async () => {
  const original = globalThis.fetch;
  globalThis.fetch = (async () =>
    new Response("nope", { status: 404 })) as typeof fetch;
  try {
    await assert.rejects(
      () => submitAnswer("d", { answer: "a", status: "decided" }),
      /not recorded/,
      "a failed answer resolved, so the interview would advance past a " +
        "question nobody answered",
    );
  } finally {
    globalThis.fetch = original;
  }
});

test("the interview advances only after the answer lands", () => {
  /** The draft is cleared and the index advanced on the success path only —
   * inside the `try`, after the await, and never in the `catch`. */
  const dispose = MORNING.slice(
    MORNING.indexOf("const dispose"),
    MORNING.indexOf("[current, draft, sending]"),
  );
  const advance = dispose.indexOf("setIndex");
  const failure = dispose.indexOf("} catch {");
  assert.ok(advance > 0 && failure > 0, "the answer path lost its shape");
  assert.ok(
    advance < failure,
    "the interview advanced on the failure path, discarding an unrecorded answer",
  );
});

// -- the extension point ---------------------------------------------------

test("every registered surface resolves to a route on disk", () => {
  /** The extension point is only safe if a typo in it fails a run rather than
   * a click. `trailingSlash: true` and `output: "export"` mean `/morning/`
   * comes from `app/morning/page.tsx`. */
  for (const { href } of SURFACES) {
    const dir = href === "/" ? APP : join(APP, href.replace(/^\/|\/$/g, ""));
    assert.ok(
      existsSync(join(dir, "page.tsx")),
      `${href} is in the nav and has no page`,
    );
  }
});

test("the morning surface carries the nav", () => {
  assert.match(MORNING, /<Nav\b/, "the morning surface lost its navigation");
});
