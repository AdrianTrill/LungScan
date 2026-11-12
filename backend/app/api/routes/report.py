"""Report endpoint: a plain-text report of a case."""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from app.core.schemas import ReportRequest
from app.deps import get_storage
from app.services.report import generate_text_report
from app.services.storage import Storage

router = APIRouter()


@router.post("/report/{case_id}")
async def generate_report(
    case_id: str, request: ReportRequest, storage: Storage = Depends(get_storage)
):
    """Save the notes and return the case's report as a text file."""
    if not storage.get_case(case_id):
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found")
    storage.save_notes(case_id, request.notes)
    report = generate_text_report(storage.get_case_detail(case_id), request.notes)
    return Response(
        content=report,
        media_type="text/plain; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="lungscan_report_{case_id[:8]}.txt"'
        },
    )
