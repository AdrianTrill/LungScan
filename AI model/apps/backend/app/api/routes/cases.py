"""Case management endpoints for listing, retrieving, and deleting cases."""

import logging
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.core.schemas import Case, CaseDetail, UploadResult
from app.core.utils import is_valid_image_type
from app.services.storage import storage

logger = logging.getLogger(__name__)
router = APIRouter()

# Directory to store uploaded images
UPLOAD_DIR = Path(__file__).parent.parent.parent.parent / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)


@router.get("/cases", response_model=list[Case])
async def list_cases():
    """Get all cases sorted by most recently updated.

    Returns:
        List of Case objects
    """
    return storage.get_all_cases()


@router.get("/cases/{case_id}", response_model=CaseDetail)
async def get_case(case_id: str):
    """Get detailed information about a specific case.

    Args:
        case_id: Unique identifier for the case

    Returns:
        CaseDetail with case info, analysis results, and notes

    Raises:
        HTTPException: If case is not found
    """
    case_detail = storage.get_case_detail(case_id)
    if not case_detail:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found")
    return case_detail


@router.delete("/cases/{case_id}")
async def delete_case(case_id: str):
    """Delete a case and all associated data.

    Args:
        case_id: Unique identifier for the case

    Returns:
        Success message

    Raises:
        HTTPException: If case is not found
    """
    success = storage.delete_case(case_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found")
    return {"message": f"Case {case_id} deleted successfully"}


@router.put("/cases/{case_id}/replace-scan", response_model=UploadResult)
async def replace_case_scan(case_id: str, scan: UploadFile = File(...)):
    """Replace the CT scan image for an existing case.
    
    This will:
    - Replace the old image file with the new one
    - Update the case filename
    - Reset the case status to "pending"
    - Clear existing analysis results (but keep notes)
    
    Args:
        case_id: Unique identifier for the case
        scan: The new image file to replace the existing scan
        
    Returns:
        UploadResult with updated case information
        
    Raises:
        HTTPException: If case is not found, file type is invalid, or upload fails
    """
    # Check if case exists
    case = storage.get_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found")
    
    # Validate file type
    if not scan.content_type or not is_valid_image_type(scan.content_type):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed types: image/jpeg, image/png, image/dicom",
        )
    
    # Get patient info if case is assigned
    patient = None
    if case.patient_id:
        patient = storage.get_patient(case.patient_id)
    
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
        
        # Save new file to disk with case_id as filename (for internal storage)
        saved_path = UPLOAD_DIR / f"{case_id}{file_extension}"
        saved_path.write_bytes(file_content)
        logger.info(f"Replaced image for case {case_id} with new file: {saved_path}")
        
        # Replace the image in storage
        updated_case = storage.replace_case_image(case_id, str(saved_path), display_filename)
        
        if not updated_case:
            raise HTTPException(status_code=500, detail="Failed to update case")
        
    except Exception as e:
        logger.error(f"Failed to replace scan for case {case_id}: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to replace scan: {str(e)}"
        )
    
    from datetime import datetime, timezone
    return UploadResult(
        case_id=case_id,
        filename=display_filename,
        patient_id=case.patient_id,
        uploaded_at=datetime.now(timezone.utc),
    )

