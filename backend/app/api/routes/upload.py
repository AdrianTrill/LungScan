"""File upload endpoint for CT slices."""

import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.core.schemas import UploadResult
from app.core.utils import display_filename, generate_case_id, read_scan
from app.deps import get_classifier, get_storage
from app.services.analysis import analyze_image
from app.services.model import Classifier, ModelUnavailableError
from app.services.storage import Storage

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/upload", response_model=UploadResult)
def upload_scan(
    scan: UploadFile = File(...),
    patient_id: str | None = Form(None),
    storage: Storage = Depends(get_storage),
    classifier: Classifier = Depends(get_classifier),
):
    """Upload a CT slice, create a case for it, and analyze it.

    If the model is unavailable the case is still created, as pending.
    """
    if patient_id and not storage.get_patient(patient_id):
        raise HTTPException(status_code=404, detail=f"Patient {patient_id} not found")
    content, extension, image = read_scan(scan)

    case_id = generate_case_id()
    storage.save_image(case_id, content, extension)
    case = storage.create_case(case_id, display_filename(scan.filename, extension), patient_id)

    try:
        storage.save_analysis_result(analyze_image(classifier, image, case_id))
    except ModelUnavailableError as error:
        logger.warning("Case %s stays pending: %s", case_id, error)
    except Exception:  # noqa: BLE001
        logger.exception("Automatic analysis failed for case %s", case_id)

    return UploadResult(
        case_id=case_id,
        filename=case.filename,
        patient_id=patient_id,
        uploaded_at=case.created_at,
    )
