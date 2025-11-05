"""File upload endpoint for CT scan images."""

from datetime import datetime, timezone

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.core.schemas import UploadResult
from app.core.utils import generate_case_id, is_valid_image_type
from app.services.storage import storage

router = APIRouter()


@router.post("/upload", response_model=UploadResult)
async def upload_scan(
    scan: UploadFile = File(...), patient_id: str | None = Form(None)
):
    """Upload a CT scan image file and create a new case.

    Args:
        scan: The uploaded image file
        patient_id: Optional patient ID to assign the case to

    Returns:
        UploadResult with case_id and metadata

    Raises:
        HTTPException: If file type is invalid or upload fails
    """
    # Validate file type
    if not scan.content_type or not is_valid_image_type(scan.content_type):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed types: image/jpeg, image/png, image/dicom",
        )

    # Validate patient_id if provided
    if patient_id and not storage.get_patient(patient_id):
        raise HTTPException(
            status_code=404, detail=f"Patient {patient_id} not found"
        )

    # Generate case ID
    case_id = generate_case_id()

    # Create case in storage
    case = storage.create_case(case_id, scan.filename, patient_id=patient_id)

    # Note: In a real application, we would save the file to disk or object storage.
    # For this MVP, we just store the metadata in memory.

    return UploadResult(
        case_id=case_id,
        filename=scan.filename,
        patient_id=patient_id,
        uploaded_at=datetime.now(timezone.utc),
    )

