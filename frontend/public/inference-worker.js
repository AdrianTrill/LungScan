/*
 * LungScan's inference worker. It loads ONNX Runtime Web and the model, and runs the model
 * off the main thread, so the page stays responsive. src/lib/inference/engine.ts drives it.
 *
 * Messages in:  { type: "init", modelUrl, cacheKey, sha256, totalBytes, ortBase, allowGpu }
 *               { type: "run", id, input }       input: Float32Array, 1x3x224x224
 * Messages out: { type: "progress", phase, loaded?, total? }
 *               { type: "ready", backend, ort }  backend: "webgpu" or "wasm"
 *               { type: "result", id, logits, cam, ms }
 *               { type: "error", id?, message }
 */
let session = null;
let backend = null;

self.onmessage = async (event) => {
  const message = event.data;
  try {
    if (message.type === "init") {
      await init(message);
      self.postMessage({ type: "ready", backend, ort: self.ort.env.versions.web });
    } else if (message.type === "run") {
      const result = await run(message.input);
      self.postMessage({ type: "result", id: message.id, ...result }, [
        result.logits.buffer,
        result.cam.buffer,
      ]);
    }
  } catch (error) {
    self.postMessage({ type: "error", id: message.id, message: String(error?.message || error) });
  }
};

async function gpuAdapter() {
  try {
    return self.navigator.gpu ? await self.navigator.gpu.requestAdapter() : null;
  } catch {
    return null;
  }
}

async function init({ modelUrl, cacheKey, sha256, totalBytes, ortBase, allowGpu }) {
  if (session) return;
  const gpu = allowGpu ? await gpuAdapter() : null;
  // The WebGPU build is twice the size of the WebAssembly one; load only what will run.
  importScripts(ortBase + (gpu ? "ort.webgpu.min.js" : "ort.wasm.min.js"));
  const ort = self.ort;
  ort.env.wasm.wasmPaths = ortBase;
  // GitHub Pages can't send the cross-origin isolation headers threads need.
  ort.env.wasm.numThreads = 1;
  // ONNX Runtime notes that it keeps shape operators on the CPU; that is expected.
  ort.env.logLevel = "error";

  const bytes = await loadModel(modelUrl, cacheKey, sha256, totalBytes);
  self.postMessage({ type: "progress", phase: "compile" });
  if (gpu) {
    try {
      session = await ort.InferenceSession.create(bytes, {
        executionProviders: ["webgpu"],
        logSeverityLevel: 3,
      });
      backend = "webgpu";
    } catch {
      session = null;
    }
  }
  if (!session) {
    session = await ort.InferenceSession.create(bytes, {
      executionProviders: ["wasm"],
      logSeverityLevel: 3,
    });
    backend = "wasm";
  }
  // The first run compiles kernels; do it now, so analyses report steady timings.
  await run(new Float32Array(3 * 224 * 224));
}

async function loadModel(url, cacheKey, sha256, totalBytes) {
  let cache = null;
  try {
    cache = await caches.open("lungscan-model");
  } catch {
    // Without Cache Storage (some private windows), the model is downloaded each visit.
  }
  const hit = cache && (await cache.match(cacheKey));
  if (hit) {
    self.postMessage({ type: "progress", phase: "cache" });
    return new Uint8Array(await hit.arrayBuffer());
  }

  const response = await fetch(url);
  if (!response.ok) throw new Error(`Could not download the model (HTTP ${response.status})`);
  const total = totalBytes || Number(response.headers.get("content-length")) || 0;
  const reader = response.body.getReader();
  const chunks = [];
  let loaded = 0;
  let reported = 0;
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    chunks.push(value);
    loaded += value.length;
    if (performance.now() - reported > 80) {
      reported = performance.now();
      self.postMessage({ type: "progress", phase: "download", loaded, total });
    }
  }
  const bytes = new Uint8Array(loaded);
  let offset = 0;
  for (const chunk of chunks) {
    bytes.set(chunk, offset);
    offset += chunk.length;
  }
  self.postMessage({ type: "progress", phase: "verify", loaded, total: loaded });
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  const hex = Array.from(new Uint8Array(digest), (b) => b.toString(16).padStart(2, "0")).join("");
  if (sha256 && hex !== sha256) throw new Error("The downloaded model does not match its manifest");
  if (cache) {
    try {
      await cache.put(cacheKey, new Response(bytes));
    } catch {
      // Over quota: keep going without the cache.
    }
  }
  return bytes;
}

async function run(input) {
  const ort = self.ort;
  const image = new ort.Tensor("float32", input, [1, 3, 224, 224]);
  const start = performance.now();
  const output = await session.run({ image });
  const ms = performance.now() - start;
  return {
    logits: new Float32Array(output.logits.data),
    cam: new Float32Array(output.cam.data),
    ms,
  };
}
