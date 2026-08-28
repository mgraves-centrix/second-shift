// Offline queue behaviour.
//
// Node 24 runs TypeScript directly and ships a test runner, so this needs one
// dependency — a fake IndexedDB — rather than a browser test stack.
//
// Rendering assertions (a disabled policy showing its reason) are verified on a
// real phone at the day-2 gates. A real device is better evidence than jsdom for
// a surface whose whole point is working on a phone.

import "fake-indexeddb/auto";
import assert from "node:assert/strict";
import test, { beforeEach } from "node:test";

import { drain, enqueue, pending, pendingCount, remove, type PendingEntry } from "../lib/queue.ts";
import { newUlid } from "../lib/ulid.ts";

const TZ = "America/Los_Angeles";

function entry(text: string, createdAt = Date.now()): PendingEntry {
  return {
    id: newUlid(createdAt),
    created_at_ms: createdAt,
    captured_tz: TZ,
    tz_offset_min: -420,
    policy: "cloud-assisted",
    text,
    modality: "text",
    capture_profile: "cloud",
  };
}

beforeEach(async () => {
  for (const item of await pending()) await remove(item.id);
  globalThis.fetch = (() => Promise.reject(new Error("offline"))) as typeof fetch;
});

test("ULID is 26 chars and embeds its instant in sortable order", () => {
  const early = newUlid(1_700_000_000_000);
  const later = newUlid(1_700_000_001_000);
  assert.equal(early.length, 26);
  assert.ok(early < later, "later ULIDs must sort after earlier ones");
});

test("ULIDs generated in the same millisecond are distinct", () => {
  const t = 1_700_000_000_000;
  const ids = new Set(Array.from({ length: 200 }, () => newUlid(t)));
  assert.equal(ids.size, 200);
});

test("capture with no network queues locally", async () => {
  await enqueue(entry("an idea captured on a train"));
  assert.equal(await pendingCount(), 1);
  const stored = (await pending())[0];
  assert.equal(stored.text, "an idea captured on a train");
});

test("two offline captures show a count of two", async () => {
  await enqueue(entry("one"));
  await enqueue(entry("two"));
  assert.equal(await pendingCount(), 2);
});

test("draining while offline sends nothing and loses nothing", async () => {
  await enqueue(entry("one"));
  await enqueue(entry("two"));
  const result = await drain("");
  assert.equal(result.sent, 0);
  assert.equal(result.remaining, 2);
});

test("reconnecting drains the queue and the count clears", async () => {
  const captured = Date.now() - 3 * 86_400_000;
  await enqueue(entry("captured three days ago", captured));
  await enqueue(entry("and another", captured + 1000));

  const seen: PendingEntry[] = [];
  globalThis.fetch = (async (_url: string, init: RequestInit) => {
    seen.push(JSON.parse(String(init.body)));
    return { ok: true, status: 201 } as Response;
  }) as unknown as typeof fetch;

  const result = await drain("");
  assert.equal(result.sent, 2);
  assert.equal(result.remaining, 0);
  assert.equal(await pendingCount(), 0);
});

test("the capture instant survives the drain unchanged", async () => {
  const captured = 1_700_000_123_456;
  await enqueue(entry("old idea", captured));

  let sent: PendingEntry | null = null;
  globalThis.fetch = (async (_url: string, init: RequestInit) => {
    sent = JSON.parse(String(init.body));
    return { ok: true, status: 201 } as Response;
  }) as unknown as typeof fetch;

  await drain("");
  assert.equal(sent!.created_at_ms, captured);
  // The identifier must still agree with it, or the server refuses the entry.
  assert.equal(sent!.id.slice(0, 10), newUlid(captured).slice(0, 10));
});

test("a replayed entry the server already holds is treated as sent", async () => {
  await enqueue(entry("already stored"));
  globalThis.fetch = (async () => ({ ok: true, status: 200 }) as Response) as unknown as typeof fetch;
  const result = await drain("");
  assert.equal(result.sent, 1);
  assert.equal(await pendingCount(), 0);
});

test("a permanently rejected entry is dropped rather than retried forever", async () => {
  await enqueue(entry("malformed somehow"));
  globalThis.fetch = (async () => ({ ok: false, status: 422 }) as Response) as unknown as typeof fetch;
  await drain("");
  assert.equal(await pendingCount(), 0);
});

test("a rate-limited entry is kept for a later attempt", async () => {
  await enqueue(entry("too fast"));
  globalThis.fetch = (async () => ({ ok: false, status: 429 }) as Response) as unknown as typeof fetch;
  await drain("");
  assert.equal(await pendingCount(), 1);
});

test("a server error keeps the entry queued", async () => {
  await enqueue(entry("server had a moment"));
  globalThis.fetch = (async () => ({ ok: false, status: 503 }) as Response) as unknown as typeof fetch;
  await drain("");
  assert.equal(await pendingCount(), 1);
});
