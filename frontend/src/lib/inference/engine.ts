/**
 * Runs the model in the browser, through public/inference-worker.js: the same ONNX file
 * the server runs, with ONNX Runtime Web on WebGPU when the browser has it, and on
 * WebAssembly otherwise. The model is downloaded once, checked against its SHA-256, and
 * kept in Cache Storage.
 */
import { asset } from "../config";

export type EnginePhase = "manifest" | "download" | "verify" | "cache" | "compile";

export interface EngineProgress {
  phase: EnginePhase;
  loaded?: number;
  total?: number;
}

export interface EngineInfo {
  backend: "webgpu" | "wasm";
  ort: string;
  source: string;
}

export interface ModelManifest {
  bytes: number;
  sha256: string;
  source: { repo: string; revision: string };
}

const CACHE = "lungscan-model";

type Pending = {
  resolve: (r: { logits: Float32Array; cam: Float32Array; ms: number }) => void;
  reject: (e: Error) => void;
};

export async function fetchManifest(): Promise<ModelManifest> {
  const response = await fetch(asset("models/lungscan.json"));
  if (!response.ok) {
    throw new Error("This build has no model: run `npm run build:browser` after exporting it");
  }
  return response.json();
}

function cacheKey(manifest: ModelManifest): string {
  return new URL(asset(`models/lungscan.onnx?sha256=${manifest.sha256}`), location.href).href;
}

class Engine {
  private worker: Worker | null = null;
  private ready: Promise<EngineInfo> | null = null;
  private listeners = new Set<(progress: EngineProgress) => void>();
  private pending = new Map<number, Pending>();
  private nextId = 1;
  info: EngineInfo | null = null;

  onProgress(listener: (progress: EngineProgress) => void): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  private emit(progress: EngineProgress) {
    this.listeners.forEach((listener) => listener(progress));
  }

  /** Load the model, once; later calls wait for the same load. */
  load(): Promise<EngineInfo> {
    if (!this.ready) {
      this.ready = this.start().catch((error) => {
        this.worker?.terminate();
        this.worker = null;
        this.ready = null;
        throw error;
      });
    }
    return this.ready;
  }

  private async start(): Promise<EngineInfo> {
    this.emit({ phase: "manifest" });
    const manifest = await fetchManifest();
    const source = `${manifest.source.repo}@${manifest.source.revision.slice(0, 7)}`;
    const worker = new Worker(asset("inference-worker.js"));
    this.worker = worker;
    return new Promise<EngineInfo>((resolve, reject) => {
      worker.onmessage = (event: MessageEvent) => {
        const message = event.data;
        if (message.type === "progress") {
          this.emit({ phase: message.phase, loaded: message.loaded, total: message.total });
        } else if (message.type === "ready") {
          this.info = { backend: message.backend, ort: message.ort, source };
          resolve(this.info);
        } else if (message.type === "result") {
          this.pending.get(message.id)?.resolve(message);
          this.pending.delete(message.id);
        } else if (message.type === "error") {
          const error = new Error(message.message);
          if (message.id && this.pending.has(message.id)) {
            this.pending.get(message.id)!.reject(error);
            this.pending.delete(message.id);
          } else {
            reject(error);
          }
        }
      };
      worker.onerror = (event) => reject(new Error(event.message || "The model worker failed"));
      worker.postMessage({
        type: "init",
        modelUrl: asset("models/lungscan.onnx"),
        cacheKey: cacheKey(manifest),
        sha256: manifest.sha256,
        totalBytes: manifest.bytes,
        ortBase: new URL(asset("ort/"), location.href).href,
        allowGpu: true,
      });
    });
  }

  async run(input: Float32Array): Promise<{ logits: Float32Array; cam: Float32Array; ms: number }> {
    await this.load();
    const id = this.nextId++;
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject });
      this.worker!.postMessage({ type: "run", id, input }, [input.buffer]);
    });
  }

  runtimeName(): string {
    if (!this.info) return "ONNX Runtime Web (this browser)";
    const device = this.info.backend === "webgpu" ? "WebGPU" : "WebAssembly";
    return `ONNX Runtime Web ${this.info.ort} (${device}, this browser)`;
  }

  /** Whether the model is already in Cache Storage. */
  async isCached(): Promise<boolean> {
    try {
      const manifest = await fetchManifest();
      const cache = await caches.open(CACHE);
      return Boolean(await cache.match(cacheKey(manifest)));
    } catch {
      return false;
    }
  }

  async clearCache(): Promise<void> {
    await caches.delete(CACHE);
  }
}

export const engine = new Engine();
