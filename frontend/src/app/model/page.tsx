"use client";

import { useEffect, useState } from "react";
import toast from "react-hot-toast";
import PageHeader from "@/components/shell/PageHeader";
import Button from "@/components/ui/Button";
import Icon from "@/components/ui/Icon";
import Spinner from "@/components/ui/Spinner";
import { Chip } from "@/components/ui/Status";
import { api, type ModelStatus } from "@/lib/api";
import { REPO_URL, RUNTIME } from "@/lib/config";
import { megabytes, percent } from "@/lib/format";
import { useEvaluation, type Int8Agreement } from "@/lib/hooks";
import { engine, type EngineProgress } from "@/lib/inference/engine";
import { LABEL_SHORT, LABELS } from "@/lib/labels";

function Tile({
  label,
  value,
  detail,
  tone = "text-ink",
}: {
  label: string;
  value: string;
  detail: string;
  tone?: string;
}) {
  return (
    <div className="rounded-xl border border-line bg-sunken p-4">
      <p className="text-[12px] text-muted">{label}</p>
      <p className={`tabular mt-1 text-[24px] font-semibold tracking-tight ${tone}`}>{value}</p>
      <p className="mt-0.5 text-11.5 leading-snug text-muted">{detail}</p>
    </div>
  );
}

function Runtime() {
  const [status, setStatus] = useState<ModelStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [progress, setProgress] = useState<EngineProgress | null>(null);
  const [loading, setLoading] = useState(false);
  const gpu = typeof navigator !== "undefined" && "gpu" in navigator;

  const refresh = () =>
    api
      .modelStatus()
      .then(setStatus)
      .catch((e) => setError(e instanceof Error ? e.message : String(e)));
  useEffect(() => {
    void refresh();
  }, []);

  const prepare = async () => {
    setLoading(true);
    const stop = engine.onProgress(setProgress);
    try {
      const info = await engine.load();
      toast.success(`Model ready on ${info.backend === "webgpu" ? "WebGPU" : "WebAssembly"}`);
      await refresh();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Could not load the model");
    } finally {
      stop();
      setLoading(false);
      setProgress(null);
    }
  };

  const forget = async () => {
    await engine.clearCache();
    toast.success("Removed the model from this browser");
    await refresh();
  };

  return (
    <section className="panel p-5">
      <div className="flex items-center justify-between gap-3">
        <h2 className="eyebrow">Where it runs</h2>
        <Chip tone="accent">
          <Icon name={RUNTIME === "browser" ? "device" : "server"} className="h-3 w-3" />
          {RUNTIME === "browser" ? "This browser" : "Server"}
        </Chip>
      </div>
      {error ? (
        <p className="mt-3 text-[12.5px] text-flag">{error}</p>
      ) : !status ? (
        <div className="mt-3 flex items-center gap-2 text-[12.5px] text-muted">
          <Spinner /> Checking…
        </div>
      ) : (
        <dl className="mt-3 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 text-[12.5px]">
          <dt className="text-muted">Weights</dt>
          <dd className="font-mono text-ink-2">{status.source}</dd>
          <dt className="text-muted">Runtime</dt>
          <dd className="text-ink-2">{status.runtime}</dd>
          {RUNTIME === "browser" && (
            <>
              <dt className="text-muted">Device</dt>
              <dd className="text-ink-2">
                {engine.info
                  ? engine.info.backend === "webgpu"
                    ? "WebGPU"
                    : "WebAssembly (one thread)"
                  : gpu
                    ? "WebGPU when the model loads, WebAssembly otherwise"
                    : "WebAssembly (this browser has no WebGPU)"}
              </dd>
              <dt className="text-muted">Model file</dt>
              <dd className="text-ink-2">
                {status.bytes ? megabytes(status.bytes) : "–"} ·{" "}
                {status.available ? "kept in this browser" : "downloaded on the first read"}
              </dd>
            </>
          )}
          {RUNTIME === "server" && (
            <>
              <dt className="text-muted">Model file</dt>
              <dd className="text-ink-2">
                {status.available ? "on the server" : "downloaded on the first read"}
              </dd>
            </>
          )}
        </dl>
      )}
      {RUNTIME === "browser" && status && (
        <div className="mt-4 flex flex-wrap items-center gap-2">
          <Button
            variant="primary"
            size="sm"
            icon="bolt"
            disabled={loading}
            onClick={() => void prepare()}
          >
            {loading
              ? progress?.phase === "download" && progress.total
                ? `Downloading ${Math.round(((progress.loaded ?? 0) / progress.total) * 100)}%`
                : "Preparing…"
              : engine.info
                ? "Ready"
                : "Load the model now"}
          </Button>
          {status.available && (
            <Button size="sm" variant="ghost" icon="trash" onClick={() => void forget()}>
              Remove from this browser
            </Button>
          )}
        </div>
      )}
    </section>
  );
}

function Checks({ removed, int8 }: { removed: number | null; int8: Int8Agreement | null }) {
  const sameReads = !int8
    ? "They are compared with the published float32 weights on the validation and test slices."
    : int8.same_flag === int8.images && int8.same_class === int8.images
      ? `On all ${int8.images} validation and test slices, every flag and every class matches the published float32 weights.`
      : `On the ${int8.images} validation and test slices, ${int8.same_flag} flags and ${int8.same_class} classes match the published float32 weights.`;
  const checks = [
    [
      "Same numbers as PyTorch",
      "The exporter writes the file only if ONNX Runtime reproduces PyTorch's logits and autograd's Grad-CAM; the largest differences are 3.3×10⁻⁶ and 5.1×10⁻⁷.",
    ],
    [
      "A third of the size, the same reads",
      `The convolutions are stored as int8 blocks, so the file is 29 MB instead of 96. ${sameReads}`,
    ],
    [
      "Same read in the browser",
      "A bit-exact port of Pillow's resize prepares each slice, and on every push headless Chrome reads sample slices in the page and compares them with the server's reads.",
    ],
    [
      "Pinned and verified",
      "The weights come from a pinned Hugging Face revision, and every download of the model, to the server or to a browser, is checked against its SHA-256.",
    ],
    [
      "Measured without copies",
      `${removed ?? "The"} test images that copy training images or each other are left out, and CI re-runs the evaluation from a fresh export, requiring the same numbers.`,
    ],
  ];

  return (
    <section className="panel p-5">
      <h2 className="eyebrow">How it is checked</h2>
      <ul className="mt-3 space-y-3 text-[12.5px] leading-relaxed text-ink-2">
        {checks.map(([title, text]) => (
          <li key={title} className="flex gap-2.5">
            <Icon name="check" className="mt-0.5 h-4 w-4 flex-none text-clear" />
            <span>
              <span className="font-medium text-ink">{title}. </span>
              {text}
            </span>
          </li>
        ))}
      </ul>
      <p className="mt-4 flex items-center gap-2 border-t border-line pt-3 text-[12px] text-muted">
        <Icon name="info" className="h-3.5 w-3.5 flex-none" />
        Research software, not a medical device. Never use it for diagnosis.
      </p>
    </section>
  );
}

export default function ModelPage() {
  const evaluation = useEvaluation();
  const clean = evaluation?.clean_test;
  const removed = evaluation
    ? Object.entries(evaluation.data.test_removed)
        .filter(([k]) => !k.startsWith("from_"))
        .reduce((sum, [, v]) => sum + v, 0)
    : 0;
  const int8 = evaluation?.int8_weights
    ? [evaluation.int8_weights.validation, evaluation.int8_weights.full_test].reduce((a, b) => ({
        images: a.images + b.images,
        same_flag: a.same_flag + b.same_flag,
        same_class: a.same_class + b.same_class,
      }))
    : null;

  return (
    <div className="mx-auto max-w-[1100px] px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
      <PageHeader eyebrow="About the classifier" title="Model">
        A ResNet-50 that reads one axial CT slice into four classes, exported to ONNX with its
        Grad-CAM map computed in the same forward pass.
      </PageHeader>

      <div className="mt-6 grid gap-4 lg:grid-cols-[1.3fr_1fr]">
        <Checks removed={evaluation ? removed : null} int8={int8} />
        <Runtime />
      </div>

      <section className="panel mt-4 p-5">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h2 className="eyebrow">Measured on the published test split</h2>
          {evaluation && (
            <p className="text-[12px] text-muted">
              {clean?.images} unique slices of {evaluation.data.images.test}; {removed} copies of
              training images or of each other removed
            </p>
          )}
        </div>
        {!clean ? (
          <div className="mt-4 flex items-center gap-2 text-[12.5px] text-muted">
            <Spinner /> Loading the evaluation…
          </div>
        ) : (
          <>
            <div className="mt-4 grid grid-cols-2 gap-3 lg:grid-cols-4">
              <Tile
                label="Cancers flagged"
                value={`${clean.cancer_vs_normal.sensitivity.k} / ${clean.cancer_vs_normal.sensitivity.n}`}
                detail={`95% CI ${percent(clean.cancer_vs_normal.sensitivity.ci95[0])} to ${percent(clean.cancer_vs_normal.sensitivity.ci95[1])}`}
                tone="text-flag"
              />
              <Tile
                label="Normal slices cleared"
                value={`${clean.cancer_vs_normal.specificity.k} / ${clean.cancer_vs_normal.specificity.n}`}
                detail={`95% CI ${percent(clean.cancer_vs_normal.specificity.ci95[0])} to ${percent(clean.cancer_vs_normal.specificity.ci95[1])}: too few to measure`}
                tone="text-clear"
              />
              <Tile
                label="Subtype, on cancers"
                value={percent(clean.subtype_on_cancers.accuracy)}
                detail={`chance is ${percent(clean.subtype_on_cancers.chance)}`}
                tone="text-caution"
              />
              <Tile
                label="Four classes"
                value={percent(clean.four_class.accuracy)}
                detail="accuracy over all classes"
              />
            </div>
            <div className="mt-5 overflow-x-auto">
              <table className="mx-auto text-[12.5px]">
                <thead>
                  <tr>
                    <th className="px-2 py-1 text-left text-11 font-normal text-muted">
                      Truth ↓ · read →
                    </th>
                    {LABELS.map((l) => (
                      <th key={l} className="px-2 py-1 text-11.5 font-medium text-ink-2">
                        {LABEL_SHORT[l]}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {clean.four_class.confusion.map((row, i) => {
                    const total = row.reduce((a, b) => a + b, 0);
                    return (
                      <tr key={LABELS[i]}>
                        <th className="px-2 py-1 text-left text-11.5 font-medium text-ink-2">
                          {LABEL_SHORT[LABELS[i]]}{" "}
                          <span className="font-normal text-faint">({total})</span>
                        </th>
                        {row.map((n, j) => (
                          <td key={j} className="p-0.5">
                            <div
                              className={`tabular grid h-10 w-16 place-items-center rounded-md ${
                                i === j ? "text-ink" : "text-ink-2"
                              }`}
                              style={{
                                background: `rgb(var(${i === j ? "--clear" : "--flag"}) / ${total ? (n / total) * 0.45 : 0})`,
                              }}
                            >
                              {n}
                            </div>
                          </td>
                        ))}
                      </tr>
                    );
                  })}
                </tbody>
              </table>
              <p className="mt-2 text-center text-11.5 text-muted">
                Most cancers are called large cell carcinoma, so the app shows subtypes as guesses.
              </p>
            </div>
          </>
        )}
      </section>

      <section className="panel mt-4 p-5">
        <h2 className="eyebrow">How a read works</h2>
        <ol className="mt-3 grid gap-3 text-[12.5px] leading-relaxed text-ink-2 md:grid-cols-2">
          {[
            [
              "Preprocess",
              "Resize the slice to 250×250, then 256×256, and crop the central 224×224: the model's own training pipeline, bit for bit in both runtimes.",
            ],
            [
              "Classify",
              "ResNet-50 gives four probabilities. The cancer probability is the sum of the three cancer classes; at 50% or more, the slice is flagged.",
            ],
            [
              "Explain",
              "The exported graph also computes Grad-CAM of the log-odds of cancer from the same pass: the classifier head's gradient is two matrix products, so no backward pass is needed.",
            ],
            [
              "Locate",
              "The 7×7 map, scaled by the cancer probability, becomes the heat map; cells with half the peak or more form up to three regions.",
            ],
          ].map(([title, text], k) => (
            <li key={title} className="flex gap-3 rounded-lg border border-line bg-sunken p-3">
              <span className="grid h-6 w-6 flex-none place-items-center rounded-full bg-accent/15 text-[12px] font-semibold text-accent">
                {k + 1}
              </span>
              <span>
                <span className="font-medium text-ink">{title}. </span>
                {text}
              </span>
            </li>
          ))}
        </ol>
        <div className="mt-4 flex flex-wrap gap-x-5 gap-y-1 text-[12.5px]">
          <a
            className="inline-flex items-center gap-1 text-accent hover:underline"
            href={`${REPO_URL}/blob/main/docs/MODEL.md`}
            target="_blank"
            rel="noopener noreferrer"
          >
            The model card <Icon name="external" className="h-3.5 w-3.5" />
          </a>
          <a
            className="inline-flex items-center gap-1 text-accent hover:underline"
            href="https://huggingface.co/dorsar/lung-cancer-detection"
            target="_blank"
            rel="noopener noreferrer"
          >
            Weights on Hugging Face (MIT) <Icon name="external" className="h-3.5 w-3.5" />
          </a>
          <a
            className="inline-flex items-center gap-1 text-accent hover:underline"
            href={`${REPO_URL}/tree/main/AI%20model`}
            target="_blank"
            rel="noopener noreferrer"
          >
            The 3D segmentation research <Icon name="external" className="h-3.5 w-3.5" />
          </a>
        </div>
      </section>
    </div>
  );
}
