"""Analysis endpoint for running AI analysis on uploaded scans."""

from fastapi import APIRouter, HTTPException

from app.core.schemas import AnalyzeResult
from app.services.analysis_mock import mock_analyze
from app.services.storage import storage

router = APIRouter()


@router.post("/analyze/{case_id}", response_model=AnalyzeResult)
async def analyze_case(case_id: str):
    """Run AI analysis on a case and return detected nodules.

    Args:
        case_id: Unique identifier for the case

    Returns:
        AnalyzeResult with detected nodules and malignancy scores

    Raises:
        HTTPException: If case is not found
    """
    # Check if case exists
    case = storage.get_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found")

    # Run mock analysis (deterministic based on case_id)
    # Using standard CT scan dimensions (can be adjusted based on actual images)
    result = mock_analyze(case_id, image_width=512, image_height=512)

    # Save analysis result
    storage.save_analysis_result(result)

    # Update case status
    storage.update_case_status(case_id, "analyzed")

    return result

