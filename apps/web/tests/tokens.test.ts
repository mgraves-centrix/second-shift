/**
 * The token system, asserted so it cannot drift back.
 *
 * This capability exists because eight tokens lived in `globals.css` and six
 * more had been declared inside `scrubber.module.css` — including `--severe`, a
 * severity color the capture surface knew nothing about. That was not
 * carelessness: the scrubber needed a color and had nowhere to put it. A
 * convention would fail the same way, so these are tests.
 */
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";

const APP = join(import.meta.dirname, "..", "app");
const COMPONENTS = join(import.meta.dirname, "..", "components");

/** Every `--name:` declaration in a stylesheet, ignoring `var(--name)` reads. */
function declaredTokens(css: string): string[] {
  return [...css.matchAll(/^\s*(--[a-z0-9-]+)\s*:/gm)].map((m) => m[1]);
}

function stylesheets(dir: string): string[] {
  const out: string[] = [];
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) out.push(...stylesheets(path));
    else if (entry.name.endsWith(".css")) out.push(path);
  }
  return out;
}

const COLOR = /^#|rgb|hsl/i;

test("every token is declared in tokens.css", () => {
  const tokens = declaredTokens(readFileSync(join(APP, "tokens.css"), "utf8"));
  assert.ok(tokens.includes("--bg"), "the palette moved out of tokens.css");
  assert.ok(tokens.includes("--severe"), "the scrubber's severity color did not move in");
});

test("no other stylesheet declares a color token", () => {
  const offenders: string[] = [];
  for (const path of [...stylesheets(APP), ...stylesheets(COMPONENTS)]) {
    if (path.endsWith("tokens.css")) continue;
    const css = readFileSync(path, "utf8");
    for (const [line] of css.matchAll(/^\s*--[a-z0-9-]+\s*:\s*([^;]+);/gm)) {
      const value = line.split(":").slice(1).join(":").trim();
      if (COLOR.test(value)) offenders.push(`${path}: ${line.trim()}`);
    }
  }
  assert.deepEqual(offenders, [], "a component declared its own color");
});

test("globals.css carries no surface layout", () => {
  /**
   * `button { width: 100% }` and `main { max-width: 34rem }` were capture's
   * layout applied to every surface that would ever exist. A new surface had to
   * opt out rather than opt in, and the scrubber was already working around it.
   */
  const css = readFileSync(join(APP, "globals.css"), "utf8");
  for (const selector of ["main", "button", "textarea", "fieldset", "legend", "h1"]) {
    assert.ok(
      !new RegExp(`^\\s*${selector}\\s*[,{]`, "m").test(css),
      `globals.css still styles bare \`${selector}\`, so every surface inherits it`,
    );
  }
});

test("the scrubber's layout values stay with the scrubber", () => {
  /** Layout is not a token. Moving `--lane-h` into the palette would put a
   * component's internals in a file every surface reads. */
  const css = readFileSync(
    join(COMPONENTS, "scrubber", "scrubber.module.css"), "utf8",
  );
  const declared = declaredTokens(css);
  assert.ok(declared.includes("--lane-h"));
  assert.ok(!declared.includes("--severe"), "the color should have moved out");
});
