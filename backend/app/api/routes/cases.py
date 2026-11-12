"""Case endpoints: list, read, delete, replace the scan, and save notes."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.core.schemas import Case, CaseDetail, NotesUpdate, UploadResult
from app.core.utils import display_filename, read_scan
from app.deps import get_storage
from app.services.storage import Storage

router = APIRouter()


@router.get("/cases", response_model=list[Case])
async def list_cases(storage: Storage = Depends(get_storage)):
    """All cases, most recently updated first."""
    return storage.get_all_cases()


@router.get("/cases/{case_id}", response_model=CaseDetail)
async def get_case(case_id: str, storage: Storage = Depends(get_storage)):
    """A case with its patient, analysis result, and notes."""
    detail = storage.get_case_detail(case_id)
    if not detail:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found")
    return detail


@router.delete("/cases/{case_id}")
async def delete_case(case_id: str, storage: Storage = Depends(get_storage)):
    """Delete a case, its image, result, and notes."""
    if not storage.delete_case(case_id):
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found")
    return {"message": f"Case {case_id} deleted successfully"}


@router.put("/cases/{case_id}/replace-scan", response_model=UploadResult)
def replace_case_scan(
    case_id: str, scan: UploadFile = File(...), storage: Storage = Depends(get_storage)
):
    """Replace a case's slice. The case goes back to pending; its notes are kept."""
    case = storage.get_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found")
    content, extension, _ = read_scan(scan)
    updated = storage.replace_case_image(
        case_id, content, extension, display_filename(scan.filename, extension)
    )
    return UploadResult(
        case_id=case_id,
        filename=updated.filename,
        patient_id=updated.patient_id,
        uploaded_at=datetime.now(timezone.utc),
    )


@router.put("/cases/{case_id}/notes")
async def save_notes(case_id: str, body: NotesUpdate, storage: Storage = Depends(get_storage)):
    """Save the reader's notes for a case."""
    if not storage.get_case(case_id):
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found")
    storage.save_notes(case_id, body.notes)
    return {"message": "Notes saved"}
