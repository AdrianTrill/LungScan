"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef } from "react";
import { relativeTime, shortId } from "@/lib/format";
import { LABEL_SHORT } from "@/lib/labels";
import { routes } from "@/lib/routes";
import type { Case, Patient } from "@/lib/types";
import Icon from "../ui/Icon";
import { ProbabilityBar, StatusChip } from "../ui/Status";
import Thumbnail from "./Thumbnail";

/** Whether the model's flag matches a sample's dataset label. */
function LabelCell({ study }: { study: Case }) {
  if (!study.dataset_label) return <span className="text-faint">–</span>;
  const truthCancer = study.dataset_label !== "normal";
  const agrees = study.status === "analyzed" ? study.flagged === truthCancer : null;
  return (
    <span className="inline-flex items-center gap-1.5 whitespace-nowrap text-ink-2">
      {agrees !== null && (
        <Icon
          name={agrees ? "check" : "close"}
          className={`h-3.5 w-3.5 ${agrees ? "text-clear" : "text-flag"}`}
          strokeWidth={2.4}
        />
      )}
      {LABEL_SHORT[study.dataset_label]}
    </span>
  );
}

export default function StudyTable({
  studies,
  patients,
  selected,
  onSelect,
}: {
  studies: Case[];
  /** Patients by ID, or null to leave out the patient column. */
  patients: Map<string, Patient> | null;
  selected: number;
  onSelect: (index: number) => void;
}) {
  const router = useRouter();
  const body = useRef<HTMLTableSectionElement>(null);

  useEffect(() => {
    body.current
      ?.querySelector<HTMLElement>(`[data-index="${selected}"]`)
      ?.scrollIntoView({ block: "nearest" });
  }, [selected]);

  return (
    <div className="panel overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full min-w-[640px] text-left">
          <thead>
            <tr className="border-b border-line text-[11px] uppercase tracking-[0.07em] text-muted">
              <th className="py-2.5 pl-4 pr-3 font-semibold">Study</th>
              {patients && <th className="px-3 py-2.5 font-semibold">Patient</th>}
              <th className="px-3 py-2.5 font-semibold">Model read</th>
              <th
                className="px-3 py-2.5 font-semibold"
                title="Ground truth, for the sample slices from the test split"
              >
                Label
              </th>
              <th className="px-3 py-2.5 font-semibold">Updated</th>
              <th className="w-8" />
            </tr>
          </thead>
          <tbody ref={body}>
            {studies.map((study, index) => {
              const patient = study.patient_id ? patients?.get(study.patient_id) : undefined;
              const active = index === selected;
              return (
                <tr
                  key={study.id}
                  data-index={index}
                  data-testid="study-row"
                  onMouseEnter={() => onSelect(index)}
                  onClick={() => router.push(routes.study(study.id))}
                  className={`group cursor-pointer border-b border-line/70 transition last:border-0 ${
                    active ? "bg-accent/[0.06]" : "hover:bg-line/30"
                  }`}
                >
                  <td className="relative py-2.5 pl-4 pr-3">
                    {active && (
                      <span className="absolute inset-y-2 left-0 w-[3px] rounded-r bg-accent" />
                    )}
                    <div className="flex items-center gap-3">
                      <Thumbnail study={study} />
                      <div className="min-w-0">
                        <Link
                          href={routes.study(study.id)}
                          onClick={(event) => event.stopPropagation()}
                          className="block max-w-[260px] truncate text-[13px] font-medium text-ink hover:text-accent"
                        >
                          {study.filename}
                        </Link>
                        <span className="font-mono text-[11px] text-faint">
                          {shortId(study.id)}
                        </span>
                      </div>
                    </div>
                  </td>
                  {patients && (
                    <td className="px-3 py-2.5">
                      {patient ? (
                        <div>
                          <div className="text-[13px] text-ink">
                            {patient.first_name} {patient.last_name}
                          </div>
                          <div className="font-mono text-[11px] text-muted">
                            {patient.medical_record_number || "–"}
                          </div>
                        </div>
                      ) : (
                        <span className="text-[12.5px] text-faint">Unassigned</span>
                      )}
                    </td>
                  )}
                  <td className="px-3 py-2.5">
                    <div className="flex items-center gap-3">
                      <ProbabilityBar value={study.cancer_probability} className="w-24" />
                      <StatusChip study={study} />
                    </div>
                  </td>
                  <td className="px-3 py-2.5 text-[12.5px]">
                    <LabelCell study={study} />
                  </td>
                  <td
                    className="whitespace-nowrap px-3 py-2.5 text-[12.5px] text-muted"
                    title={study.updated_at}
                  >
                    {relativeTime(study.updated_at)}
                  </td>
                  <td className="pr-3 text-faint group-hover:text-ink-2">
                    <Icon name="next" />
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
