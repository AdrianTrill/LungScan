"""Health check and model information."""

from fastapi import APIRouter, Depends

from app.deps import get_classifier
from app.services.model import LABEL_NAMES, LABELS, MODEL_NAME, Classifier

router = APIRouter()


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok"}


@router.get("/model")
def model_info(classifier: Classifier = Depends(get_classifier)):
    """Which model the server runs, and whether its file is present yet."""
    return {
        "name": MODEL_NAME,
        "source": classifier.source,
        "runtime": classifier.runtime,
        "available": classifier.model_path.exists(),
        "labels": [{"id": label, "name": LABEL_NAMES[label]} for label in LABELS],
    }
