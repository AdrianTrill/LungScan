"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import toast from "react-hot-toast";
import UploadDialog from "@/components/dialogs/UploadDialog";
import StudyTable from "@/components/studies/StudyTable";
import Button from "@/components/ui/Button";
import Spinner from "@/components/ui/Spinner";
import { Empty } from "@/components/ui/Status";
import { api } from "@/lib/api";
import { ageFrom, formatDate } from "@/lib/format";
import { useResource, useShortcuts } from "@/lib/hooks";
import { routes } from "@/lib/routes";

function Patient({ id }: { id: string }) {
  const router = useRouter();
  const detail = useResource(() => api.getPatient(id), [id]);
  const [uploading, setUploading] = useState(false);
  const [selected, setSelected] = useState(0);

  useShortcuts({ n: () => setUploading(true) });

  if (detail.loading && !detail.data) {
    return (
      <div className="flex h-[60vh] items-center justify-center gap-2 text-muted">
        <Spinner /> Loading the patient…
      </div>
    );
  }
  if (!detail.data) {
    return (
      <div className="mx-auto max-w-3xl px-6 py-16">
        <Empty
          title="Patient not found"
          action={
            <Link href={routes.patients}>
              <Button icon="back">All patients</Button>
            </Link>
          }
        >
          {detail.error?.message}
        </Empty>
      </div>
    );
  }

  const { patient, cases } = detail.data;
  const name = `${patient.first_name} ${patient.last_name}`;
  const remove = async () => {
    if (!confirm(`Delete ${name}?`)) return;
    try {
      await api.deletePatient(patient.id);
      toast.success(`${name} deleted`);
      router.push(routes.patients);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not delete the patient");
    }
  };

  const facts: [string, string][] = [
    ["Record", patient.medical_record_number || "–"],
    ["Born", `${formatDate(patient.date_of_birth)} · ${ageFrom(patient.date_of_birth)} years`],
    ["Studies", String(cases.length)],
    ["Flagged", String(cases.filter((c) => c.flagged).length)],
  ];

  return (
    <div className="mx-auto max-w-[1280px] px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
      <Link href={routes.patients} className="text-[12.5px] text-muted hover:text-ink">
        ← All patients
      </Link>
      <div className="panel mt-3 flex flex-col gap-5 p-5 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-4">
          <span className="grid h-14 w-14 place-items-center rounded-2xl bg-accent/15 text-[18px] font-semibold text-accent">
            {patient.first_name[0]}
            {patient.last_name[0]}
          </span>
          <div>
            <h1 className="text-[22px] font-semibold tracking-tight text-ink">{name}</h1>
            <dl className="mt-1 flex flex-wrap gap-x-5 gap-y-1 text-[12.5px]">
              {facts.map(([k, v]) => (
                <div key={k} className="flex gap-1.5">
                  <dt className="text-muted">{k}</dt>
                  <dd className={`text-ink-2 ${k === "Record" ? "font-mono" : ""}`}>{v}</dd>
                </div>
              ))}
            </dl>
          </div>
        </div>
        <div className="flex gap-2">
          <Button
            icon="trash"
            variant="danger"
            disabled={cases.length > 0}
            onClick={() => void remove()}
            title={cases.length ? "Patients with studies cannot be deleted" : "Delete the patient"}
          >
            Delete
          </Button>
          <Button variant="primary" icon="plus" shortcut="N" onClick={() => setUploading(true)}>
            New study
          </Button>
        </div>
      </div>

      <h2 className="eyebrow mb-2 mt-7">Studies</h2>
      {cases.length ? (
        <StudyTable studies={cases} patients={null} selected={selected} onSelect={setSelected} />
      ) : (
        <Empty
          title="No studies yet"
          action={
            <Button variant="primary" icon="plus" onClick={() => setUploading(true)}>
              New study
            </Button>
          }
        >
          Add a CT slice for {patient.first_name}.
        </Empty>
      )}

      <UploadDialog
        open={uploading}
        onClose={() => setUploading(false)}
        patientId={patient.id}
        onUploaded={(caseId) => router.push(`${routes.study(caseId)}&analyze=1`)}
      />
    </div>
  );
}

function PatientFromQuery() {
  const id = useSearchParams().get("id");
  return id ? <Patient key={id} id={id} /> : <Empty title="No patient selected" />;
}

export default function PatientPage() {
  return (
    <Suspense>
      <PatientFromQuery />
    </Suspense>
  );
}
