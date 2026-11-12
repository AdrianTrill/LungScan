/**
 * Plain-text case reports, as backend/app/services/report.py writes them, so a report
 * exported in the browser reads like one from the server.
 */
import { probability } from "./format";
import { LABEL_NAMES } from "./labels";
import type { CaseDetail, Label } from "./types";

const RULE = "=".repeat(64);
const THIN = "-".repeat(64);

function when(iso: string | Date): string {
  const date = typeof iso === "string" ? new Date(iso) : iso;
  return `${date.toISOString().slice(0, 16).replace("T", " ")} UTC`;
}

export function reportFilename(caseId: string): string {
  return `lungscan_report_${caseId.slice(0, 8)}.txt`;
}

export function generateTextReport(
  detail: CaseDetail,
  notes: string,
  generatedAt = new Date()
): string {
  const { case: study, patient, analysis_result: result } = detail;
  const who = patient
    ? [
        `${patient.first_name} ${patient.last_name}`,
        ...(patient.medical_record_number ? [patient.medical_record_number] : []),
        `born ${patient.date_of_birth}`,
      ].join(", ")
    : "Unassigned";

  const lines = [
    RULE,
    "LUNGSCAN REPORT",
    RULE,
    "",
    `Case ID:      ${study.id}`,
    `Study:        ${study.filename}`,
    `Patient:      ${who}`,
    `Report date:  ${when(generatedAt)}`,
    `Status:       ${study.status.toUpperCase()}`,
    "",
    THIN,
    "MODEL READ (research software, not for clinical use)",
    THIN,
    "",
  ];
  if (result) {
    lines.push(
      result.summary,
      "",
      `Cancer probability:  ${probability(result.cancer_probability)}`
    );
    lines.push("Class probabilities:");
    for (const [label, value] of Object.entries(result.probabilities)) {
      lines.push(`  ${LABEL_NAMES[label as Label].padEnd(26)}${probability(value).padStart(7)}`);
    }
    lines.push("");
    if (result.regions.length) {
      lines.push("Regions where the Grad-CAM evidence for cancer peaks:");
      result.regions.forEach((region, k) => {
        lines.push(
          `  ${k + 1}. center (${region.x}, ${region.y}), radius ${region.radius} px, ` +
            `evidence ${probability(region.evidence)}`
        );
        lines.push(`     ${region.explanation}`);
      });
      lines.push("");
    }
    lines.push(
      `Model:     ${result.model.name}, ${result.model.source}`,
      `Runtime:   ${result.model.runtime}`,
      `Analyzed:  ${when(result.analyzed_at)}`,
      ""
    );
  } else {
    lines.push("The slice has not been analyzed.", "");
  }
  lines.push(
    THIN,
    "NOTES",
    THIN,
    "",
    notes.trim() || "(No notes provided)",
    "",
    RULE,
    "LungScan is research software. It is not a medical device, and its",
    "output must not be used for diagnosis.",
    RULE,
    ""
  );
  return lines.join("\n");
}
