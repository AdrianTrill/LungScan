"use client";

import { useRouter } from "next/navigation";
import { useMemo, useRef, useState } from "react";
import UploadDialog from "@/components/dialogs/UploadDialog";
import PageHeader from "@/components/shell/PageHeader";
import StudyTable from "@/components/studies/StudyTable";
import Button from "@/components/ui/Button";
import Icon from "@/components/ui/Icon";
import Spinner from "@/components/ui/Spinner";
import { Empty } from "@/components/ui/Status";
import { api } from "@/lib/api";
import { RUNTIME } from "@/lib/config";
import { useResource, useShortcuts } from "@/lib/hooks";
import { routes } from "@/lib/routes";
import type { Case, Patient } from "@/lib/types";

type Filter = "all" | "flagged" | "cleared" | "pending";

const FILTERS: { id: Filter; label: string; test: (c: Case) => boolean }[] = [
  { id: "all", label: "All", test: () => true },
  { id: "flagged", label: "Flagged", test: (c) => c.status === "analyzed" && !!c.flagged },
  { id: "cleared", label: "Cleared", test: (c) => c.status === "analyzed" && !c.flagged },
  { id: "pending", label: "Awaiting read", test: (c) => c.status === "pending" },
];

function Stat({
  label,
  value,
  tone,
  hint,
}: {
  label: string;
  value: number | string;
  tone?: string;
  hint?: string;
}) {
  return (
    <div className="panel px-4 py-3">
      <p className="text-[12px] text-muted">{label}</p>
      <p
        className={`tabular mt-0.5 text-[22px] font-semibold tracking-tight ${tone ?? "text-ink"}`}
      >
        {value}
      </p>
      {hint && <p className="text-11.5 text-faint">{hint}</p>}
    </div>
  );
}

function matches(study: Case, patient: Patient | undefined, query: string): boolean {
  if (!query) return true;
  const haystack = [
    study.filename,
    study.id,
    patient?.first_name,
    patient?.last_name,
    patient?.medical_record_number,
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
  return query
    .toLowerCase()
    .split(/\s+/)
    .every((term) => haystack.includes(term));
}

export default function WorklistPage() {
  const router = useRouter();
  const cases = useResource(() => api.listCases(), []);
  const patients = useResource(() => api.listPatients(), []);
  const [filter, setFilter] = useState<Filter>("all");
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState(0);
  const [uploading, setUploading] = useState(false);
  const search = useRef<HTMLInputElement>(null);

  const byId = useMemo(() => new Map((patients.data ?? []).map((p) => [p.id, p])), [patients.data]);
  const all = useMemo(() => cases.data ?? [], [cases.data]);
  const shown = useMemo(
    () =>
      all.filter(
        (c) =>
          FILTERS.find((f) => f.id === filter)!.test(c) &&
          matches(c, c.patient_id ? byId.get(c.patient_id) : undefined, query.trim())
      ),
    [all, filter, query, byId]
  );
  const count = (id: Filter) => all.filter(FILTERS.find((f) => f.id === id)!.test).length;
  const index = Math.min(selected, Math.max(0, shown.length - 1));

  useShortcuts({
    "/": () => search.current?.focus(),
    n: () => setUploading(true),
    j: () => setSelected(Math.min(shown.length - 1, index + 1)),
    ArrowDown: () => setSelected(Math.min(shown.length - 1, index + 1)),
    k: () => setSelected(Math.max(0, index - 1)),
    ArrowUp: () => setSelected(Math.max(0, index - 1)),
    Enter: () => shown[index] && router.push(routes.study(shown[index].id)),
  });

  return (
    <div className="mx-auto max-w-[1280px] px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
      <PageHeader
        eyebrow="Reading room"
        title="Worklist"
        actions={
          <Button variant="primary" icon="plus" shortcut="N" onClick={() => setUploading(true)}>
            New study
          </Button>
        }
      >
        {RUNTIME === "browser"
          ? "Axial CT slices, read by a ResNet-50 running in this browser. Nothing leaves the page."
          : "Axial CT slices, read by a ResNet-50 on the LungScan server."}
      </PageHeader>

      <div className="mt-6 grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat label="Studies" value={all.length} hint={`${byId.size} patients`} />
        <Stat
          label="Flagged by the model"
          value={count("flagged")}
          tone="text-flag"
          hint="cancer probability ≥ 50%"
        />
        <Stat label="Cleared" value={count("cleared")} tone="text-clear" hint="reads as normal" />
        <Stat
          label="Awaiting read"
          value={count("pending")}
          tone="text-caution"
          hint="not analyzed yet"
        />
      </div>

      <div className="mt-6 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div
          className="flex gap-1 rounded-lg border border-line bg-surface p-1"
          role="tablist"
          aria-label="Filter"
        >
          {FILTERS.map((f) => (
            <button
              key={f.id}
              type="button"
              role="tab"
              aria-selected={filter === f.id}
              onClick={() => {
                setFilter(f.id);
                setSelected(0);
              }}
              className={`rounded-md px-3 py-1.5 text-[12.5px] font-medium transition ${
                filter === f.id ? "bg-raised text-ink shadow-panel" : "text-muted hover:text-ink"
              }`}
            >
              {f.label}
              <span className="tabular ml-1.5 text-faint">{count(f.id)}</span>
            </button>
          ))}
        </div>
        <label className="relative block sm:w-72">
          <Icon
            name="search"
            className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-faint"
          />
          <input
            ref={search}
            value={query}
            onChange={(event) => {
              setQuery(event.target.value);
              setSelected(0);
            }}
            onKeyDown={(event) =>
              event.key === "Escape" && (setQuery(""), event.currentTarget.blur())
            }
            placeholder="Search patient, record, or file"
            className="field h-9 pl-9 pr-8"
            aria-label="Search the worklist"
          />
          <kbd className="kbd absolute right-2 top-1/2 -translate-y-1/2">/</kbd>
        </label>
      </div>

      <div className="mt-3">
        {cases.loading && !cases.data ? (
          <div className="flex items-center justify-center gap-2 py-20 text-muted">
            <Spinner /> Loading the worklist…
          </div>
        ) : cases.error ? (
          <Empty title="The worklist could not be loaded">{cases.error.message}</Empty>
        ) : shown.length === 0 ? (
          <Empty
            title={all.length ? "No studies match" : "No studies yet"}
            action={
              !all.length && (
                <Button variant="primary" icon="plus" onClick={() => setUploading(true)}>
                  New study
                </Button>
              )
            }
          >
            {all.length
              ? "Try another filter or search."
              : "Add a CT slice to have the model read it."}
          </Empty>
        ) : (
          <StudyTable studies={shown} patients={byId} selected={index} onSelect={setSelected} />
        )}
      </div>

      <p className="mt-3 hidden text-11.5 text-faint sm:block">
        <kbd className="kbd">J</kbd> <kbd className="kbd">K</kbd> move ·{" "}
        <kbd className="kbd">Enter</kbd> opens · <kbd className="kbd">?</kbd> all shortcuts
      </p>

      <UploadDialog
        open={uploading}
        onClose={() => setUploading(false)}
        onUploaded={(id) => router.push(`${routes.study(id)}&analyze=1`)}
      />
    </div>
  );
}
