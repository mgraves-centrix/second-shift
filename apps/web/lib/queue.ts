// The offline queue.
//
// An entry is written to IndexedDB BEFORE any network attempt, complete: its
// identifier, capture instant, timezone and policy are all fixed at that moment.
// Draining is a replay of finished records, not a deferred construction — which
// is what lets the server treat a duplicate as a lookup rather than a merge.
//
// This works offline only because a service worker caches the app shell. Without
// a secure context there is no service worker, the page cannot load with no
// network, and none of this is reachable. See Spike A.

const DB_NAME = "second-shift";
const STORE = "pending";
const VERSION = 1;

export interface PendingEntry {
  id: string;
  created_at_ms: number;
  captured_tz: string;
  tz_offset_min: number;
  policy: string;
  text: string;
  modality: "text";
  capture_profile: string | null;
}

function open(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, VERSION);
    request.onupgradeneeded = () => {
      const db = request.result;
      if (!db.objectStoreNames.contains(STORE)) {
        db.createObjectStore(STORE, { keyPath: "id" });
      }
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

function tx<T>(mode: IDBTransactionMode, run: (store: IDBObjectStore) => IDBRequest<T>): Promise<T> {
  return open().then(
    (db) =>
      new Promise<T>((resolve, reject) => {
        const request = run(db.transaction(STORE, mode).objectStore(STORE));
        request.onsuccess = () => resolve(request.result);
        request.onerror = () => reject(request.error);
      }),
  );
}

export const enqueue = (entry: PendingEntry) => tx("readwrite", (s) => s.put(entry));
export const remove = (id: string) => tx("readwrite", (s) => s.delete(id));
export const pending = () => tx<PendingEntry[]>("readonly", (s) => s.getAll());
export const pendingCount = () => tx<number>("readonly", (s) => s.count());

export interface DrainResult {
  sent: number;
  remaining: number;
}

/** Replay every queued entry. A 4xx other than 429 is permanent — stop retrying it. */
export async function drain(apiBase: string): Promise<DrainResult> {
  const items = await pending();
  let sent = 0;
  for (const item of items) {
    try {
      const response = await fetch(`${apiBase}/entries`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(item),
      });
      if (response.ok) {
        // 201 created or 200 replayed — both mean the server holds it.
        await remove(item.id);
        sent += 1;
      } else if (response.status >= 400 && response.status < 500 && response.status !== 429) {
        // The server will never accept this. Keeping it would retry forever.
        await remove(item.id);
      }
    } catch {
      break; // still offline; leave the rest queued
    }
  }
  return { sent, remaining: await pendingCount() };
}
