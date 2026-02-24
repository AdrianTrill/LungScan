"""Report generation endpoint for exporting case reports."""

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from app.core.schemas import ReportRequest
from app.services.report import generate_text_report
from app.services.storage import storage

router = APIRouter()


@router.post("/report/{case_id}")
async def generate_report(case_id: str, request: ReportRequest):
    """Generate and download a report for a case.

    Args:
        case_id: Unique identifier for the case
        request: ReportRequest containing notes

    Returns:
        Text file response with the generated report

    Raises:
        HTTPException: If case is not found
    """
    # Check if case exists
    case = storage.get_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found")

    # Save notes
    storage.save_notes(case_id, request.notes)

    # Generate report
    try:
        report_text = generate_text_report(case_id, request.notes)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Generate filename
    filename = f"lungscan_report_{case_id[:8]}.txt"

    return Response(
        content=report_text,
        media_type="text/plain",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

