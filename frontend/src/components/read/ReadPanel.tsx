"use client";

import type { AnalyzeProgress } from "@/lib/api";
import { RUNTIME } from "@/lib/config";
import { formatDateTime, megabytes, percent, probability } from "@/lib/format";
import type { Evaluation } from "@/lib/hooks";
import { LABEL_NAMES, LABELS } from "@/lib/labels";
import type { AnalyzeResult, Case } from "@/lib/types";
import Button from "../ui/Button";
import Icon, { type IconName } from "../ui/Icon";
import Spinner from "../ui/Spinner";
import { Chip } from "../ui/Status";

function Gauge({ value, flagged }: { value: number; flagged: boolean }) {
  const r = 30;
  const circumference = 2 * Math.PI * r;
  return (
    <div className="relative h-[84px] w-[84px] flex-none">
      <svg viewBox="0 0 80 80" className="h-full w-full -rotate-90">
        <circle cx="40" cy="40" r={r} fill="none" stroke="rgb(var(--line))" strokeWidth="7" />
        <circle
          cx="40"
          cy="40"
          r={r}
          fill="none"
          stroke={flagged ? "rgb(var(--flag))" : "rgb(var(--clear))"}
          strokeWidth="7"
          strokeLinecap="round"
          strokeDasharray={`${Math.max(0.01, value) * circumference} ${circumference}`}
          className="transition-[stroke-dasharray] duration-700"
        />
      </svg>
      <div className="absolute inset-0 grid place-items-center">
        <span
          className={`tabular font-semibold tracking-tight text-ink ${
            probability(value).length > 5 ? "text-[15px]" : "text-[17px]"
          }`}
        >
          {probability(value)}
        </span>
      </div>
    </div>
  );
}

function runtimeChip(runtime: string): { label: string; icon: IconName } {
  if (runtime.includes("precomputed")) return { label: "Precomputed sample", icon: "file" };
  if (runtime.includes("this browser")) {
    return {
      label: runtime.includes("WebGPU") ? "This browser · WebGPU" : "This browser · WebAssembly",
      icon: "device",
    };
  }
  return { label: "Server", icon: "server" };
}

function Agreement({ study, result }: { study: Case; result: AnalyzeResult }) {
  const label = study.dataset_label;
  if (!label) return null;
  const truthCancer = label !== "normal";
  let tone: "clear" | "flag" | "caution";
  let text: string;
  if (!truthCancer) {
    [tone, text] = result.flagged
      ? ["flag", "False alarm: the dataset labels this slice normal."]
      : ["clear", "The read agrees with the dataset label."];
  } else if (!result.flagged) {
    [tone, text] = ["flag", "Missed: the model reads this cancer slice as normal."];
  } else if (result.subtype === label) {
    [tone, text] = ["clear", "The read agrees with the dataset label, subtype included."];
  } else {
    [tone, text] = ["caution", "Flagged correctly, but the subtype guess is wrong."];
  }
  const colors = { clear: "text-clear", flag: "text-flag", caution: "text-caution" };
  return (
    <div
      className="mt-3 rounded-lg border border-line bg-sunken px-3 py-2.5"
      data-testid="agreement"
    >
      <div className="flex items-center justify-between gap-2">
        <span className="eyebrow">Dataset label</span>
        <span className="text-[12.5px] font-medium text-ink">{LABEL_NAMES[label]}</span>
      </div>
      <p className={`mt-1 flex items-start gap-1.5 text-[12.5px] ${colors[tone]}`}>
        <Icon name={tone === "clear" ? "check" : "alert"} className="mt-[2px] h-3.5 w-3.5" />
        {text}
      </p>
      <p className="mt-1 text-[11.5px] text-muted">
        A held-out slice from the model&apos;s test split.
      </p>
    </div>
  );
}

const PHASES: Record<AnalyzeProgress["phase"], string> = {
  manifest: "Checking the model",
  download: "Downloading the model, once",
  verify: "Checking the download's SHA-256",
  cache: "Loading the model from this browser",
  compile: "Starting ONNX Runtime Web",
  analyze: "Reading the slice",
};

function Progress({ progress }: { progress: AnalyzeProgress | null }) {
  const phase = progress?.phase ?? "analyze";
  const fraction = progress?.total ? Math.min(1, (progress.loaded ?? 0) / progress.total) : null;
  return (
    <div
      className="rounded-lg border border-accent/25 bg-accent/[0.06] p-3"
      data-testid="analysis-progress"
    >
      <div className="flex items-center gap-2 text-[13px] font-medium text-accent">
        <Spinner className="h-4 w-4" />
        {PHASES[phase]}
      </div>
      {phase === "download" && (
        <>
          <div className="mt-2.5 h-1.5 overflow-hidden rounded-full bg-line">
            <div
              className="h-full rounded-full bg-accent transition-[width]"
              style={{ width: `${(fraction ?? 0) * 100}%` }}
            />
          </div>
          <p className="tabular mt-1.5 text-[11.5px] text-muted">
            {megabytes(progress?.loaded ?? 0)}
            {progress?.total ? ` of ${megabytes(progress.total)}` : ""} · kept in this browser for
            next time
          </p>
        </>
      )}
    </div>
  );
}

export default function ReadPanel({
  study,
  result,
  evaluation,
  analyzing,
  progress,
  error,
  onAnalyze,
  highlight,
  onHighlight,
  onFocus,
}: {
  study: Case;
  result: AnalyzeResult | null;
  evaluation: Evaluation | null;
  analyzing: boolean;
  progress: AnalyzeProgress | null;
  error: string | null;
  onAnalyze: () => void;
  highlight: string | null;
  onHighlight: (id: string | null) => void;
  onFocus: (id: string) => void;
}) {
  const subtypeStats = evaluation?.clean_test.subtype_on_cancers;
  const chip = result ? runtimeChip(result.model.runtime) : null;
  const best = result ? Math.max(...LABELS.map((l) => result.probabilities[l])) : 0;

  return (
    <section className="panel p-4" aria-label="Model read" data-testid="read-panel">
      <div className="flex items-center justify-between gap-2">
        <h2 className="eyebrow">Model read</h2>
        {chip && (
          <Chip tone="accent">
            <Icon name={chip.icon} className="h-3 w-3" />
            {chip.label}
          </Chip>
        )}
      </div>

      {analyzing && (
        <div className="mt-3">
          <Progress progress={progress} />
        </div>
      )}
      {error && !analyzing && (
        <div className="mt-3 flex gap-2 rounded-lg border border-flag/30 bg-flag/10 p-3 text-[12.5px] text-flag">
          <Icon name="alert" className="mt-0.5 h-4 w-4" />
          <span>{error}</span>
        </div>
      )}

      {!result && !analyzing && (
        <div className="mt-3 rounded-lg border border-dashed border-line-strong p-4 text-center">
          <p className="text-[13px] font-medium text-ink">Not read yet</p>
          <p className="mx-auto mt-1 max-w-[270px] text-[12px] text-muted">
            {RUNTIME === "browser"
              ? "The model runs in this browser. The first read downloads it (29 MB) and keeps it for next time."
              : "The server runs the model on this slice."}
          </p>
          <Button variant="primary" icon="scan" shortcut="A" className="mt-3" onClick={onAnalyze}>
            Analyze slice
          </Button>
        </div>
      )}

      {result && (
        <div className={analyzing ? "opacity-50" : ""}>
          <div className="mt-3 flex items-center gap-4">
            <Gauge value={result.cancer_probability} flagged={result.flagged} />
            <div className="min-w-0">
              <p className="text-[11.5px] text-muted">Cancer probability</p>
              <p
                className={`text-[16px] font-semibold leading-snug ${result.flagged ? "text-flag" : "text-clear"}`}
                data-testid="verdict"
                data-cancer-probability={result.cancer_probability}
              >
                {result.flagged ? "Flagged: reads as cancer" : "Not flagged: reads as normal"}
              </p>
              {result.subtype && (
                <p className="mt-0.5 text-[12px] text-ink-2">
                  Subtype guess: {LABEL_NAMES[result.subtype]}
                  <span className="text-muted"> (unreliable)</span>
                </p>
              )}
            </div>
          </div>

          <Agreement study={study} result={result} />

          <div className="mt-4">
            <h3 className="eyebrow mb-2">Class probabilities</h3>
            <div className="space-y-1.5">
              {LABELS.map((label) => {
                const value = result.probabilities[label];
                const normal = label === "normal";
                return (
                  <div
                    key={label}
                    className="grid grid-cols-[1fr_88px_52px] items-center gap-2 text-[12.5px]"
                  >
                    <span className={value === best ? "font-medium text-ink" : "text-ink-2"}>
                      {LABEL_NAMES[label]}
                    </span>
                    <span className="h-1.5 overflow-hidden rounded-full bg-line">
                      <span
                        className={`block h-full rounded-full ${normal ? "bg-clear" : "bg-flag/80"}`}
                        style={{ width: `${Math.max(1.5, value * 100)}%` }}
                      />
                    </span>
                    <span className="tabular text-right text-ink-2">{probability(value)}</span>
                  </div>
                );
              })}
            </div>
            {subtypeStats && (
              <p className="mt-2 text-[11.5px] leading-snug text-muted">
                Subtype guesses were right {percent(subtypeStats.accuracy)} of the time on{" "}
                {subtypeStats.n} unique test cancers, where chance is {percent(subtypeStats.chance)}
                .
              </p>
            )}
          </div>

          {result.regions.length > 0 && (
            <div className="mt-4">
              <h3 className="eyebrow mb-2">Regions · Grad-CAM peaks</h3>
              <ul className="space-y-1.5">
                {result.regions.map((region, k) => (
                  <li key={region.id}>
                    <button
                      type="button"
                      onMouseEnter={() => onHighlight(region.id)}
                      onMouseLeave={() => onHighlight(null)}
                      onFocus={() => onHighlight(region.id)}
                      onBlur={() => onHighlight(null)}
                      onClick={() => onFocus(region.id)}
                      className={`flex w-full items-start gap-2.5 rounded-lg border px-2.5 py-2 text-left transition ${
                        highlight === region.id
                          ? "border-cyan-400/50 bg-cyan-400/[0.07]"
                          : "border-line hover:border-line-strong"
                      }`}
                      title="Show this region in the viewer"
                    >
                      <span className="mt-0.5 grid h-5 w-5 flex-none place-items-center rounded-full bg-cyan-300 text-[11px] font-bold text-cyan-950">
                        {k + 1}
                      </span>
                      <span className="min-w-0">
                        <span className="flex items-center gap-2 text-[12.5px] font-medium text-ink">
                          Evidence {probability(region.evidence)}
                          <span className="font-normal text-muted">
                            · {region.cells} of 49 cells · r {region.radius} px
                          </span>
                        </span>
                        <span className="mt-0.5 block text-[11.5px] leading-snug text-muted">
                          {region.explanation}
                        </span>
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
              <p className="mt-2 text-[11.5px] leading-snug text-muted">
                Where the model&apos;s evidence concentrates, not detected nodules.
              </p>
            </div>
          )}

          <p className="mt-4 text-[12.5px] leading-relaxed text-ink-2">{result.summary}</p>

          <dl className="mt-4 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 border-t border-line pt-3 text-[11.5px]">
            <dt className="text-muted">Model</dt>
            <dd className="truncate font-mono text-ink-2">{result.model.source}</dd>
            <dt className="text-muted">Runtime</dt>
            <dd className="text-ink-2">{result.model.runtime}</dd>
            <dt className="text-muted">Inference</dt>
            <dd className="tabular text-ink-2">{result.inference_ms.toFixed(1)} ms</dd>
            <dt className="text-muted">Read</dt>
            <dd className="text-ink-2">{formatDateTime(result.analyzed_at)}</dd>
          </dl>
        </div>
      )}
    </section>
  );
}
