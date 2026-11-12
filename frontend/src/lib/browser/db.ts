/** A small promise wrapper around IndexedDB, where the browser runtime keeps its data. */

const NAME = "lungscan";
const VERSION = 1;

export type StoreName = "patients" | "cases" | "results" | "notes" | "images" | "meta";

let opening: Promise<IDBDatabase> | null = null;

function open(): Promise<IDBDatabase> {
  if (!opening) {
    opening = new Promise((resolve, reject) => {
      const request = indexedDB.open(NAME, VERSION);
      request.onupgradeneeded = () => {
        const db = request.result;
        db.createObjectStore("patients", { keyPath: "id" });
        db.createObjectStore("cases", { keyPath: "id" });
        db.createObjectStore("results", { keyPath: "case_id" });
        db.createObjectStore("notes");
        db.createObjectStore("images");
        db.createObjectStore("meta");
      };
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => {
        opening = null;
        reject(request.error ?? new Error("IndexedDB is not available in this browser"));
      };
    });
  }
  return opening;
}

async function transact<T>(
  store: StoreName,
  mode: IDBTransactionMode,
  action: (s: IDBObjectStore) => IDBRequest<T>
): Promise<T> {
  const db = await open();
  return new Promise<T>((resolve, reject) => {
    const tx = db.transaction(store, mode);
    const request = action(tx.objectStore(store));
    tx.oncomplete = () => resolve(request.result);
    tx.onerror = () => reject(tx.error ?? request.error);
    tx.onabort = () => reject(tx.error ?? new Error("IndexedDB transaction aborted"));
  });
}

export function get<T>(store: StoreName, key: IDBValidKey): Promise<T | undefined> {
  return transact<T | undefined>(store, "readonly", (s) => s.get(key));
}

export function getAll<T>(store: StoreName): Promise<T[]> {
  return transact<T[]>(store, "readonly", (s) => s.getAll());
}

export async function put(store: StoreName, value: unknown, key?: IDBValidKey): Promise<void> {
  await transact(store, "readwrite", (s) => s.put(value, key));
}

export async function remove(store: StoreName, key: IDBValidKey): Promise<void> {
  await transact(store, "readwrite", (s) => s.delete(key));
}

export async function clearAll(): Promise<void> {
  const stores: StoreName[] = ["patients", "cases", "results", "notes", "images", "meta"];
  for (const store of stores) await transact(store, "readwrite", (s) => s.clear());
}
