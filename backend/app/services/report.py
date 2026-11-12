"""Plain-text case reports.

frontend/src/lib/report.ts writes the same report in the browser.
"""

from datetime import datetime, timezone

from app.core.schemas import CaseDetail
from app.services.analysis import probability
from app.services.model import LABEL_NAMES

RULE = "=" * 64
THIN = "-" * 64


def _when(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def generate_text_report(
    detail: CaseDetail, notes: str, generated_at: datetime | None = None
) -> str:
    """A plain-text report of a case: the study, the model's read, and the notes."""
    case = detail.case
    patient = detail.patient
    result = detail.analysis_result
    generated_at = generated_at or datetime.now(timezone.utc)

    if patient:
        parts = [f"{patient.first_name} {patient.last_name}"]
        if patient.medical_record_number:
            parts.append(patient.medical_record_number)
        parts.append(f"born {patient.date_of_birth}")
        who = ", ".join(parts)
    else:
        who = "Unassigned"

    lines = [
        RULE,
        "LUNGSCAN REPORT",
        RULE,
        "",
        f"Case ID:      {case.id}",
        f"Study:        {case.filename}",
        f"Patient:      {who}",
        f"Report date:  {_when(generated_at)}",
        f"Status:       {case.status.upper()}",
        "",
        THIN,
        "MODEL READ (research software, not for clinical use)",
        THIN,
        "",
    ]
    if result:
        lines += [
            result.summary,
            "",
            f"Cancer probability:  {probability(result.cancer_probability)}",
        ]
        lines.append("Class probabilities:")
        for label, value in result.probabilities.items():
            lines.append(f"  {LABEL_NAMES[label]:<26}{probability(value):>7}")
        lines.append("")
        if result.regions:
            lines.append("Regions where the Grad-CAM evidence for cancer peaks:")
            for k, region in enumerate(result.regions, start=1):
                lines.append(
                    f"  {k}. center ({region.x}, {region.y}), radius {region.radius} px, "
                    f"evidence {probability(region.evidence)}"
                )
                lines.append(f"     {region.explanation}")
            lines.append("")
        lines += [
            f"Model:     {result.model.name}, {result.model.source}",
            f"Runtime:   {result.model.runtime}",
            f"Analyzed:  {_when(result.analyzed_at)}",
            "",
        ]
    else:
        lines += ["The slice has not been analyzed.", ""]

    lines += [
        THIN,
        "NOTES",
        THIN,
        "",
        notes.strip() or "(No notes provided)",
        "",
        RULE,
        "LungScan is research software. It is not a medical device, and its",
        "output must not be used for diagnosis.",
        RULE,
        "",
    ]
    return "\n".join(lines)
