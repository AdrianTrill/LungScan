"""Case management endpoints for listing, retrieving, and deleting cases."""

from fastapi import APIRouter, HTTPException

from app.core.schemas import Case, CaseDetail
from app.services.storage import storage

router = APIRouter()


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

