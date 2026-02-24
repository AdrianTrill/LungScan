"""Report generation service for creating downloadable reports."""

from datetime import datetime

from app.core.schemas import AnalyzeResult, Case
from app.services.storage import storage


def generate_text_report(case_id: str, notes: str) -> str:
    """Generate a plain text report combining case info, analysis, and notes.

    Args:
        case_id: Case identifier
        notes: Doctor's notes to include

    Returns:
        Formatted text report as a string
    """
    case_detail = storage.get_case_detail(case_id)
    if not case_detail:
        raise ValueError(f"Case {case_id} not found")

    case = case_detail.case
    analysis = case_detail.analysis_result

    # Build report header
    report_lines = [
        "=" * 60,
        "LUNGSCAN ASSIST - MEDICAL REPORT",
        "=" * 60,
        "",
        f"Case ID: {case.id}",
        f"Patient Scan: {case.filename}",
        f"Report Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}",
        f"Case Status: {case.status.upper()}",
        "",
        "-" * 60,
        "ANALYSIS RESULTS",
        "-" * 60,
        "",
    ]

    if analysis:
        report_lines.append(analysis.summary)
        report_lines.append("")
        report_lines.append(f"Detected Nodules: {len(analysis.nodules)}")
        report_lines.append("")

        for i, nodule in enumerate(analysis.nodules, 1):
            report_lines.append(f"Nodule {i}:")
            report_lines.append(f"  Position: ({nodule.x}, {nodule.y})")
            report_lines.append(f"  Size: {nodule.radius}px radius")
            report_lines.append(f"  Malignancy Score: {nodule.malignancy_score:.3f}")
            report_lines.append(f"  Notes: {nodule.explanation}")
            report_lines.append("")
    else:
        report_lines.append("No analysis results available.")
        report_lines.append("")

    report_lines.extend([
        "-" * 60,
        "CLINICAL NOTES",
        "-" * 60,
        "",
        notes if notes.strip() else "(No notes provided)",
        "",
        "=" * 60,
        "End of Report",
        "=" * 60,
    ])

    return "\n".join(report_lines)

