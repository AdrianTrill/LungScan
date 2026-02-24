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

    # Validate patient_id if provided and get patient info
    patient = None
    if patient_id:
        patient = storage.get_patient(patient_id)
        if not patient:
            raise HTTPException(
                status_code=404, detail=f"Patient {patient_id} not found"
            )

    # Generate case ID
    case_id = generate_case_id()

    # Read file content
    try:
        file_content = await scan.read()
        
        # Determine filename - use patient name if available, otherwise use original filename
        file_extension = Path(scan.filename).suffix or ".jpg"
        if patient:
            # Create filename: "FirstName_LastName_CT_Scan_caseid.ext"
            patient_name = f"{patient.first_name}_{patient.last_name}".replace(" ", "_")
            safe_filename = "".join(c for c in patient_name if c.isalnum() or c in ("_", "-")).strip()
            display_filename = f"{safe_filename}_CT_Scan_{case_id}{file_extension}"
        else:
            # Use original filename but prefix with case_id for uniqueness
            original_name = Path(scan.filename).stem
            display_filename = f"{original_name}_{case_id}{file_extension}"
        
        # Save file to disk with case_id as filename (for internal storage)
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

    # Create case in storage with display filename and patient_id
    case = storage.create_case(case_id, display_filename, patient_id=patient_id)

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
        filename=display_filename,  # Return the display filename (with patient name if applicable)
        patient_id=patient_id,
        uploaded_at=datetime.now(timezone.utc),
    )

