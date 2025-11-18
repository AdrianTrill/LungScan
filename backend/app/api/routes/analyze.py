"""Analysis endpoint for running AI analysis on uploaded scans."""

import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException

from app.core.schemas import AnalyzeResult
from app.services.analysis import analyze_image
from app.services.storage import storage

logger = logging.getLogger(__name__)
router = APIRouter()

# Shared uploads directory (same as upload route)
UPLOAD_DIR = Path(__file__).parent.parent.parent.parent / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)


@router.post("/analyze/{case_id}", response_model=AnalyzeResult)
async def analyze_case(case_id: str):
    """Run AI analysis on a case and return detected nodules.

    Args:
        case_id: Unique identifier for the case

    Returns:
        AnalyzeResult with detected nodules and malignancy scores

    Raises:
        HTTPException: If case is not found or image is not available
    """
    # Check if case exists
    case = storage.get_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found")

    # Get image path
    image_path = storage.get_image_path(case_id)

    # If path missing or file deleted, try to locate file in uploads directory
    if not image_path or not Path(image_path).exists():
        possible_files = sorted(UPLOAD_DIR.glob(f"{case_id}.*"))
        if possible_files:
            image_path = str(possible_files[0])
            storage.save_image_path(case_id, image_path)
            logger.info(
                "Recovered image path for case %s from uploads directory: %s",
                case_id,
                image_path,
            )

    if not image_path or not Path(image_path).exists():
        # Fallback: try to use sample image for demo cases
        if case_id == "case-004":
            # Use sample image from static directory
            sample_image = Path(__file__).parent.parent.parent.parent / "static" / "images" / "ct_scan_sample.png"
            if sample_image.exists():
                image_path = str(sample_image)
                logger.info(f"Using sample image for case {case_id}")
            else:
                raise HTTPException(
                    status_code=404,
                    detail=f"Image not found for case {case_id}. Please upload an image first.",
                )
        else:
            raise HTTPException(
                status_code=404,
                detail=f"Image not found for case {case_id}. Please upload an image first.",
            )

    try:
        # Run AI analysis using the real model
        logger.info(f"Running AI analysis for case {case_id} using image: {image_path}")
        result = analyze_image(image_path=Path(image_path), case_id=case_id)

        # Save analysis result
        storage.save_analysis_result(result)

        # Update case status
        storage.update_case_status(case_id, "analyzed")

        return result
    except Exception as e:
        logger.error(f"Analysis failed for case {case_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Analysis failed: {str(e)}. Please try again or contact support.",
        )

