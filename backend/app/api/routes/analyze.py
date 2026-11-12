"""Analysis endpoint: run the classifier on a case's slice."""

import logging

from fastapi import APIRouter, Depends, HTTPException

from app.core.schemas import AnalyzeResult
from app.deps import get_classifier, get_storage
from app.services.analysis import analyze_image
from app.services.model import Classifier, ModelUnavailableError, load_rgb
from app.services.storage import Storage

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/analyze/{case_id}", response_model=AnalyzeResult)
def analyze_case(
    case_id: str,
    storage: Storage = Depends(get_storage),
    classifier: Classifier = Depends(get_classifier),
):
    """Analyze a case's slice and store the result."""
    if not storage.get_case(case_id):
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found")
    path = storage.image_path(case_id)
    if not path or not path.exists():
        raise HTTPException(status_code=404, detail=f"Case {case_id} has no image to analyze")
    try:
        image = load_rgb(path)
    except OSError as error:
        raise HTTPException(status_code=422, detail="The case's image cannot be read") from error
    try:
        result = analyze_image(classifier, image, case_id)
    except ModelUnavailableError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    storage.save_analysis_result(result)
    logger.info("Case %s: cancer probability %.3f", case_id, result.cancer_probability)
    return result
