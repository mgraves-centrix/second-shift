// What a browser test stands on: a seeded night, a running orchestrator, and a
// real browser, all local and all torn down.
//
// Hermetic by construction. The database is a fresh file in a temporary
// directory, the port is one the kernel hands out, and the only network is
// localhost. Nothing here can reach the always-on machine, and nothing needs a
// credential: the night is the synthetic generator's, and no model is called.

import { spawn, spawnSync, type ChildProcess } from "node:child_process";
import { existsSync, mkdtempSync, rmSync } from "node:fs";
import { createServer } from "node:net";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";

import { chromium, type Browser } from "playwright-core";

const WEB = resolve(import.meta.dirname, "..");
const API = resolve(WEB, "..", "api");

/** The interpreter with the orchestrator installed. Overridable for CI. */
const PYTHON = process.env.GATE_PYTHON ?? join(API, ".venv", "bin", "python");

/** How long the orchestrator gets to answer before the test says it did not. */
const READY_WITHIN_MS = 30_000;

export interface Orchestrator {
  url: string;
  stop: () => Promise<void>;
}

function freePort(): Promise<number> {
  return new Promise((done, fail) => {
    const server = createServer();
    server.unref();
    server.on("error", fail);
    server.listen(0, "127.0.0.1", () => {
      const address = server.address();
      server.close(() =>
        typeof address === "object" && address ? done(address.port) : fail(new Error("no port")),
      );
    });
  });
}

function requireBuilt(): void {
  if (!existsSync(PYTHON)) {
    throw new Error(
      `no orchestrator interpreter at ${PYTHON} — create apps/api/.venv (see the ` +
        "README) or set GATE_PYTHON",
    );
  }
  if (!existsSync(join(WEB, "out", "night", "index.html"))) {
    throw new Error(
      "the web export is missing (apps/web/out) — run `npm --prefix apps/web run build` first; " +
        "the orchestrator serves the export, and a browser test against no pages would " +
        "fail as a timeout that says nothing",
    );
  }
}

/** Seed one synthetic night into a fresh database and serve it. */
export async function startOrchestrator(seed = 42): Promise<Orchestrator> {
  requireBuilt();
  const dir = mkdtempSync(join(tmpdir(), "second-shift-e2e-"));
  const db = join(dir, "e2e.db");

  const seeded = spawnSync(PYTHON, ["-m", "secondshift_seed", "--seed", String(seed), "--db", db], {
    encoding: "utf8",
  });
  if (seeded.status !== 0) {
    rmSync(dir, { recursive: true, force: true });
    throw new Error(`seeding the night failed (exit ${seeded.status}):\n${seeded.stderr}`);
  }

  const port = await freePort();
  const url = `http://127.0.0.1:${port}`;
  let stderr = "";
  const child: ChildProcess = spawn(
    PYTHON,
    ["-m", "uvicorn", "secondshift.api.main:app", "--host", "127.0.0.1", "--port", String(port)],
    {
      env: { ...process.env, SECOND_SHIFT_DB: db, SECOND_SHIFT_SYNTHETIC: "1" },
      stdio: ["ignore", "ignore", "pipe"],
    },
  );
  child.stderr?.on("data", (chunk) => {
    stderr = (stderr + String(chunk)).slice(-4000);
  });

  const stop = async () => {
    if (child.exitCode === null) {
      const exited = new Promise((done) => child.once("exit", done));
      child.kill("SIGTERM");
      await exited;
    }
    rmSync(dir, { recursive: true, force: true });
  };

  // Waited for by asking, never by sleeping. A process that exits early is
  // reported with its own words, not as a timeout.
  const deadline = Date.now() + READY_WITHIN_MS;
  while (Date.now() < deadline) {
    if (child.exitCode !== null) {
      await stop();
      throw new Error(`the orchestrator exited (${child.exitCode}) before answering:\n${stderr}`);
    }
    try {
      const response = await fetch(`${url}/capabilities`);
      if (response.ok) return { url, stop };
    } catch {
      // Not listening yet.
    }
    await new Promise((done) => setTimeout(done, 100));
  }
  await stop();
  throw new Error(
    `the orchestrator did not answer ${url}/capabilities within ${READY_WITHIN_MS / 1000}s:\n${stderr}`,
  );
}

/**
 * The installed Chrome, never a downloaded one.
 *
 * `playwright-core` ships no browser, and that is the point: a developer
 * machine and a CI runner both have Chrome already, and a browser download on
 * every run is minutes spent on something no test is about.
 */
export function launchBrowser(): Promise<Browser> {
  const executablePath = process.env.GATE_CHROME;
  return chromium.launch(
    executablePath ? { executablePath, headless: true } : { channel: "chrome", headless: true },
  );
}
