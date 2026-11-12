"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import toast from "react-hot-toast";
import PatientDialog from "@/components/dialogs/PatientDialog";
import PageHeader from "@/components/shell/PageHeader";
import Button from "@/components/ui/Button";
import Icon from "@/components/ui/Icon";
import Spinner from "@/components/ui/Spinner";
import { Chip, Empty } from "@/components/ui/Status";
import { api } from "@/lib/api";
import { ageFrom, formatDate, probability, relativeTime } from "@/lib/format";
import { useResource, useShortcuts } from "@/lib/hooks";
import { routes } from "@/lib/routes";
import type { Case } from "@/lib/types";

export default function PatientsPage() {
  const router = useRouter();
  const patients = useResource(() => api.listPatients(), []);
  const cases = useResource(() => api.listCases(), []);
  const [creating, setCreating] = useState(false);

  const studies = useMemo(() => {
    const map = new Map<string, Case[]>();
    for (const c of cases.data ?? []) {
      if (c.patient_id) map.set(c.patient_id, [...(map.get(c.patient_id) ?? []), c]);
    }
    return map;
  }, [cases.data]);

  useShortcuts({ n: () => setCreating(true) });

  const remove = async (id: string, name: string) => {
    if (!confirm(`Delete ${name}?`)) return;
    try {
      await api.deletePatient(id);
      toast.success(`${name} deleted`);
      await patients.reload();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not delete the patient");
    }
  };

  return (
    <div className="mx-auto max-w-[1280px] px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
      <PageHeader
        eyebrow="Records"
        title="Patients"
        actions={
          <Button variant="primary" icon="plus" shortcut="N" onClick={() => setCreating(true)}>
            New patient
          </Button>
        }
      >
        Each patient&apos;s studies, with the model&apos;s highest cancer probability among them.
      </PageHeader>

      <div className="mt-6">
        {patients.loading && !patients.data ? (
          <div className="flex items-center justify-center gap-2 py-20 text-muted">
            <Spinner /> Loading patients…
          </div>
        ) : !patients.data?.length ? (
          <Empty
            title="No patients yet"
            action={
              <Button variant="primary" icon="plus" onClick={() => setCreating(true)}>
                New patient
              </Button>
            }
          />
        ) : (
          <div className="panel overflow-x-auto">
            <table className="w-full min-w-[640px] text-left">
              <thead>
                <tr className="border-b border-line text-11 uppercase tracking-[0.07em] text-muted">
                  <th className="py-2.5 pl-4 pr-3 font-semibold">Patient</th>
                  <th className="px-3 py-2.5 font-semibold">Record</th>
                  <th className="px-3 py-2.5 font-semibold">Born</th>
                  <th className="px-3 py-2.5 font-semibold">Studies</th>
                  <th className="px-3 py-2.5 font-semibold">Highest read</th>
                  <th className="px-3 py-2.5 font-semibold">Last study</th>
                  <th className="w-12" />
                </tr>
              </thead>
              <tbody>
                {patients.data.map((p) => {
                  const own = studies.get(p.id) ?? [];
                  const reads = own.filter((c) => c.cancer_probability !== null);
                  const highest = reads.length
                    ? Math.max(...reads.map((c) => c.cancer_probability!))
                    : null;
                  const last = own.reduce<string | null>(
                    (a, c) => (!a || c.updated_at > a ? c.updated_at : a),
                    null
                  );
                  const name = `${p.first_name} ${p.last_name}`;
                  return (
                    <tr
                      key={p.id}
                      onClick={() => router.push(routes.patient(p.id))}
                      className="cursor-pointer border-b border-line/70 transition last:border-0 hover:bg-line/30"
                    >
                      <td className="py-3 pl-4 pr-3">
                        <div className="flex items-center gap-3">
                          <span className="grid h-8 w-8 place-items-center rounded-full bg-accent/15 text-[12px] font-semibold text-accent">
                            {p.first_name[0]}
                            {p.last_name[0]}
                          </span>
                          <Link
                            href={routes.patient(p.id)}
                            onClick={(e) => e.stopPropagation()}
                            className="text-[13px] font-medium text-ink hover:text-accent"
                          >
                            {p.last_name}, {p.first_name}
                          </Link>
                        </div>
                      </td>
                      <td className="px-3 py-3 font-mono text-[12px] text-ink-2">
                        {p.medical_record_number || "–"}
                      </td>
                      <td className="px-3 py-3 text-[12.5px] text-ink-2">
                        {formatDate(p.date_of_birth)}{" "}
                        <span className="text-muted">· {ageFrom(p.date_of_birth)} y</span>
                      </td>
                      <td className="tabular px-3 py-3 text-[12.5px] text-ink-2">{own.length}</td>
                      <td className="px-3 py-3">
                        {highest === null ? (
                          <span className="text-[12.5px] text-faint">–</span>
                        ) : (
                          <Chip tone={highest >= 0.5 ? "flag" : "clear"} dot>
                            {probability(highest)}
                          </Chip>
                        )}
                      </td>
                      <td className="px-3 py-3 text-[12.5px] text-muted">
                        {last ? relativeTime(last) : "–"}
                      </td>
                      <td className="pr-3">
                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation();
                            void remove(p.id, name);
                          }}
                          disabled={own.length > 0}
                          className="rounded-md p-1.5 text-faint hover:bg-flag/10 hover:text-flag disabled:pointer-events-none disabled:opacity-30"
                          title={
                            own.length
                              ? "Patients with studies cannot be deleted"
                              : `Delete ${name}`
                          }
                          aria-label={`Delete ${name}`}
                        >
                          <Icon name="trash" />
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <PatientDialog
        open={creating}
        onClose={() => setCreating(false)}
        onCreated={(p) => {
          setCreating(false);
          toast.success(`${p.first_name} ${p.last_name} added`);
          router.push(routes.patient(p.id));
        }}
      />
    </div>
  );
}
