// Copies what the app serves from public/: the sample slices and the evaluation (both
// modes), and for the in-browser build, ONNX Runtime Web and the exported model.
import { copyFileSync, cpSync, existsSync, mkdirSync, rmSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const frontend = join(dirname(fileURLToPath(import.meta.url)), "..");
const repo = join(frontend, "..");
const pub = join(frontend, "public");
const browser = process.env.NEXT_PUBLIC_RUNTIME === "browser";

rmSync(join(pub, "samples"), { recursive: true, force: true });
cpSync(join(repo, "model", "samples"), join(pub, "samples"), { recursive: true });
copyFileSync(join(repo, "model", "evaluation.json"), join(pub, "evaluation.json"));

if (browser) {
  const ort = join(frontend, "node_modules", "onnxruntime-web", "dist");
  mkdirSync(join(pub, "ort"), { recursive: true });
  for (const file of [
    "ort.wasm.min.js",
    "ort-wasm-simd-threaded.mjs",
    "ort-wasm-simd-threaded.wasm",
    "ort.webgpu.min.js",
    "ort-wasm-simd-threaded.asyncify.mjs",
    "ort-wasm-simd-threaded.asyncify.wasm",
  ]) {
    copyFileSync(join(ort, file), join(pub, "ort", file));
  }
  const model = join(repo, "model", "lungscan.onnx");
  if (existsSync(model)) {
    mkdirSync(join(pub, "models"), { recursive: true });
    copyFileSync(model, join(pub, "models", "lungscan.onnx"));
    copyFileSync(join(repo, "model", "lungscan.json"), join(pub, "models", "lungscan.json"));
  } else {
    console.warn(
      "model/lungscan.onnx is missing: the app will run, but cannot read new slices.\n" +
        "Export it with `cd backend && python -m tools.export_model`, or fetch it with `python -m tools.fetch_model`."
    );
  }
}
console.log(`Copied the samples${browser ? ", ONNX Runtime Web, and the model" : ""} into public/`);
