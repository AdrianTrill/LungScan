"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import toast from "react-hot-toast";
import NotesPanel from "@/components/read/NotesPanel";
import ReadPanel from "@/components/read/ReadPanel";
import Button from "@/components/ui/Button";
import Icon from "@/components/ui/Icon";
import Spinner from "@/components/ui/Spinner";
import { Empty, StatusChip } from "@/components/ui/Status";
import Viewer, { type ViewerFocus } from "@/components/viewer/Viewer";
import { api, type AnalyzeProgress } from "@/lib/api";
import { ageFrom, formatDate, shortId } from "@/lib/format";
import { useEvaluation, useResource, useShortcuts } from "@/lib/hooks";
import { routes } from "@/lib/routes";
import type { Patient } from "@/lib/types";

function AssignPatient({ caseId, onAssigned }: { caseId: string; onAssigned: () => void }) {
  const [patients, setPatients] = useState<Patient[]>([]);
  const [choice, setChoice] = useState("");
  useEffect(() => {
    api
      .listPatients()
      .then(setPatients)
      .catch(() => setPatients([]));
  }, []);
  const assign = async () => {
    try {
      await api.assignCase(caseId, choice);
      toast.success("Study assigned");
      onAssigned();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not assign the study");
    }
  };
  return (
    <div className="flex items-center gap-2">
      <select
        value={choice}
        onChange={(e) => setChoice(e.target.value)}
        className="field h-8 w-48 py-0 text-[12.5px]"
      >
        <option value="">Assign to a patient…</option>
        {patients.map((p) => (
          <option key={p.id} value={p.id}>
            {p.last_name}, {p.first_name}
          </option>
        ))}
      </select>
      <Button size="sm" disabled={!choice} onClick={() => void assign()}>
        Assign
      </Button>
    </div>
  );
}

function Study({ id }: { id: string }) {
  const router = useRouter();
  const params = useSearchParams();
  const detail = useResource(() => api.getCase(id), [id]);
  const list = useResource(() => api.listCases(), [id]);
  const evaluation = useEvaluation();
  const [imageUrl, setImageUrl] = useState<string | null>(null);
  const [imageVersion, setImageVersion] = useState(0);
  const [analyzing, setAnalyzing] = useState(false);
  const [progress, setProgress] = useState<AnalyzeProgress | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [highlight, setHighlight] = useState<string | null>(null);
  const [focus, setFocus] = useState<ViewerFocus | null>(null);
  const replaceInput = useRef<HTMLInputElement>(null);
  const autoStarted = useRef(false);

  const { reload: reloadDetail } = detail;
  const { reload: reloadList } = list;
  const study = detail.data?.case;
  const patient = detail.data?.patient ?? null;
  const result = detail.data?.analysis_result ?? null;

  // The image changes only when the scan is replaced, not when the slice is read again.
  useEffect(() => {
    if (!study) return;
    let live = true;
    api
      .imageUrl(study)
      .then((url) => live && setImageUrl(url))
      .catch(() => live && setImageUrl(null));
    return () => {
      live = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [study?.id, imageVersion]);

  const analyze = useCallback(async () => {
    if (analyzing) return;
    setAnalyzing(true);
    setError(null);
    setProgress(null);
    try {
      const read = await api.analyzeCase(id, setProgress);
      await reloadDetail();
      void reloadList();
      toast.success(read.flagged ? "Read complete: flagged" : "Read complete: not flagged");
    } catch (e) {
      setError(e instanceof Error ? e.message : "The analysis failed");
    } finally {
      setAnalyzing(false);
      setProgress(null);
    }
  }, [analyzing, id, reloadDetail, reloadList]);

  // A new upload arrives with ?analyze=1: read it straight away, once.
  useEffect(() => {
    if (params.get("analyze") !== "1" || !study || autoStarted.current) return;
    autoStarted.current = true;
    router.replace(routes.study(id));
    if (study.status === "pending") void analyze();
  }, [params, study, id, router, analyze]);

  const order = useMemo(() => list.data?.map((c) => c.id) ?? [], [list.data]);
  const position = order.indexOf(id);
  const go = (offset: number) => {
    const next = order[position + offset];
    if (next) router.push(routes.study(next));
  };

  const replace = async (file: File | undefined) => {
    if (!file) return;
    try {
      await api.replaceScan(id, file);
      await reloadDetail();
      setImageVersion((v) => v + 1);
      toast.success("Scan replaced");
      void analyze();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Could not replace the scan");
    }
  };

  const remove = async () => {
    if (!study || !confirm(`Delete the study “${study.filename}”, its read, and its notes?`))
      return;
    await api.deleteCase(id);
    toast.success("Study deleted");
    router.push(patient ? routes.patient(patient.id) : routes.worklist);
  };

  useShortcuts({
    a: () => void analyze(),
    "[": () => go(-1),
    "]": () => go(1),
  });

  if (detail.loading && !detail.data) {
    return (
      <div className="flex h-[70vh] items-center justify-center gap-2 text-muted">
        <Spinner /> Loading the study…
      </div>
    );
  }
  if (detail.error || !study) {
    return (
      <div className="mx-auto max-w-3xl px-6 py-16">
        <Empty
          title="Study not found"
          action={
            <Link href={routes.worklist}>
              <Button icon="back">Back to the worklist</Button>
            </Link>
          }
        >
          {detail.error?.message}
        </Empty>
      </div>
    );
  }

  const topLeft = patient
    ? [
        `${patient.last_name.toUpperCase()}, ${patient.first_name}`,
        [patient.medical_record_number, `${ageFrom(patient.date_of_birth)} y`]
          .filter(Boolean)
          .join(" · "),
      ]
    : ["UNASSIGNED"];

  return (
    <div className="flex flex-col gap-3 px-3 py-3 sm:px-4 lg:h-[calc(100vh)] lg:py-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex min-w-0 items-center gap-3">
          <Link
            href={routes.worklist}
            className="rounded-lg border border-line p-2 text-muted hover:border-line-strong hover:text-ink"
            aria-label="Back to the worklist"
            title="Back to the worklist"
          >
            <Icon name="back" />
          </Link>
          <div className="min-w-0">
            <div className="flex items-center gap-1.5 text-[12px] text-muted">
              {patient ? (
                <Link href={routes.patient(patient.id)} className="hover:text-ink">
                  {patient.first_name} {patient.last_name}
                </Link>
              ) : (
                <span>Unassigned</span>
              )}
              <span className="text-faint">/</span>
              <span className="font-mono">{shortId(study.id)}</span>
              <span className="text-faint">·</span>
              <span>{formatDate(study.created_at)}</span>
            </div>
            <div className="flex items-center gap-2.5">
              <h1 className="truncate text-[17px] font-semibold tracking-tight text-ink">
                {study.filename}
              </h1>
              <StatusChip study={study} />
            </div>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {!patient && <AssignPatient caseId={id} onAssigned={() => void reloadDetail()} />}
          <div className="flex items-center rounded-lg border border-line">
            <button
              type="button"
              onClick={() => go(-1)}
              disabled={position <= 0}
              className="p-2 text-muted hover:text-ink disabled:opacity-30"
              title="Previous study ([)"
              aria-label="Previous study"
            >
              <Icon name="prev" />
            </button>
            <span className="tabular px-1 text-11.5 text-muted">
              {position >= 0 ? `${position + 1} / ${order.length}` : "–"}
            </span>
            <button
              type="button"
              onClick={() => go(1)}
              disabled={position < 0 || position >= order.length - 1}
              className="p-2 text-muted hover:text-ink disabled:opacity-30"
              title="Next study (])"
              aria-label="Next study"
            >
              <Icon name="next" />
            </button>
          </div>
          <Button icon="upload" size="sm" onClick={() => replaceInput.current?.click()}>
            Replace scan
          </Button>
          <input
            ref={replaceInput}
            type="file"
            accept="image/png,image/jpeg"
            className="hidden"
            onChange={(event) => {
              void replace(event.target.files?.[0]);
              event.target.value = "";
            }}
          />
          <Button
            icon="trash"
            size="sm"
            variant="danger"
            onClick={() => void remove()}
            aria-label="Delete study"
          />
          <Button
            variant="primary"
            icon={result ? "refresh" : "scan"}
            shortcut="A"
            disabled={analyzing}
            onClick={() => void analyze()}
            data-testid="analyze"
          >
            {analyzing ? "Reading…" : result ? "Read again" : "Analyze"}
          </Button>
        </div>
      </div>

      <div className="grid min-h-0 flex-1 gap-3 lg:grid-cols-[minmax(0,1fr)_400px]">
        <div className="h-[62vh] min-h-0 lg:h-auto">
          <Viewer
            src={imageUrl}
            result={result}
            topLeft={topLeft}
            topRight={[study.filename.toUpperCase(), formatDate(study.created_at)]}
            scanning={analyzing}
            highlight={highlight}
            focus={focus}
          />
        </div>
        <div className="min-h-0 space-y-3 lg:overflow-y-auto lg:pr-1">
          <ReadPanel
            study={study}
            result={result}
            evaluation={evaluation}
            analyzing={analyzing}
            progress={progress}
            error={error}
            onAnalyze={() => void analyze()}
            highlight={highlight}
            onHighlight={setHighlight}
            onFocus={(regionId) => setFocus({ regionId, nonce: Date.now() })}
          />
          <NotesPanel caseId={id} initial={detail.data?.notes ?? ""} />
        </div>
      </div>
    </div>
  );
}

function StudyFromQuery() {
  const id = useSearchParams().get("id");
  if (!id) {
    return (
      <div className="mx-auto max-w-3xl px-6 py-16">
        <Empty title="No study selected" />
      </div>
    );
  }
  return <Study key={id} id={id} />;
}

export default function StudyPage() {
  return (
    <Suspense>
      <StudyFromQuery />
    </Suspense>
  );
}
