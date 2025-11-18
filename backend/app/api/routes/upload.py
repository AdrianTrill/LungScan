"""File upload endpoint for CT scan images."""

import logging
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.core.schemas import UploadResult
from app.core.utils import generate_case_id, is_valid_image_type
from app.services.analysis import analyze_image
from app.services.storage import storage

logger = logging.getLogger(__name__)
router = APIRouter()

# Directory to store uploaded images
UPLOAD_DIR = Path(__file__).parent.parent.parent.parent / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)


@router.post("/upload", response_model=UploadResult)
async def upload_scan(
    scan: UploadFile = File(...), patient_id: str | None = Form(None)
):
    """Upload a CT scan image file and create a new case.
    
    Automatically runs AI analysis after successful upload.

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

    # Read file content
    try:
        file_content = await scan.read()
        
        # Save file to disk
        file_extension = Path(scan.filename).suffix or ".jpg"
        saved_path = UPLOAD_DIR / f"{case_id}{file_extension}"
        saved_path.write_bytes(file_content)
        logger.info(f"Saved uploaded image to: {saved_path}")
        
        # Store file path in storage
        storage.save_image_path(case_id, str(saved_path))
        
    except Exception as e:
        logger.error(f"Failed to save uploaded file: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to save uploaded file: {str(e)}"
        )

    # Create case in storage
    case = storage.create_case(case_id, scan.filename, patient_id=patient_id)

    # Automatically run AI analysis after upload
    try:
        logger.info(f"Starting automatic analysis for case {case_id}")
        result = analyze_image(image_path=Path(saved_path), case_id=case_id)
        
        # Save analysis result
        storage.save_analysis_result(result)
        
        # Update case status to analyzed
        storage.update_case_status(case_id, "analyzed")
        logger.info(f"Analysis completed successfully for case {case_id}")
        
    except Exception as e:
        # If analysis fails, log the error but don't fail the upload
        # The case will remain in "pending" status and can be analyzed manually
        logger.error(
            f"Automatic analysis failed for case {case_id}: {str(e)}",
            exc_info=True
        )
        logger.warning(
            f"Case {case_id} uploaded successfully but analysis failed. "
            "Case status remains 'pending'. Analysis can be run manually."
        )

    return UploadResult(
        case_id=case_id,
        filename=scan.filename,
        patient_id=patient_id,
        uploaded_at=datetime.now(timezone.utc),
    )

