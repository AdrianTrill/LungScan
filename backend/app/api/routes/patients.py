"""Patient endpoints."""

from fastapi import APIRouter, Depends, HTTPException

from app.core.schemas import Case, Patient, PatientCreate, PatientDetail
from app.core.utils import generate_patient_id
from app.deps import get_storage
from app.services.storage import Storage

router = APIRouter()


@router.post("/patients", response_model=Patient, status_code=201)
async def create_patient(body: PatientCreate, storage: Storage = Depends(get_storage)):
    """Create a patient."""
    return storage.create_patient(
        patient_id=generate_patient_id(),
        first_name=body.first_name.strip(),
        last_name=body.last_name.strip(),
        date_of_birth=body.date_of_birth,
        medical_record_number=body.medical_record_number.strip(),
    )


@router.get("/patients", response_model=list[Patient])
async def list_patients(storage: Storage = Depends(get_storage)):
    """All patients, sorted by last name."""
    return storage.get_all_patients()


@router.get("/patients/{patient_id}", response_model=PatientDetail)
async def get_patient(patient_id: str, storage: Storage = Depends(get_storage)):
    """A patient with their cases."""
    detail = storage.get_patient_detail(patient_id)
    if not detail:
        raise HTTPException(status_code=404, detail=f"Patient {patient_id} not found")
    return detail


@router.delete("/patients/{patient_id}")
async def delete_patient(patient_id: str, storage: Storage = Depends(get_storage)):
    """Delete a patient who has no cases."""
    if storage.delete_patient(patient_id):
        return {"message": f"Patient {patient_id} deleted successfully"}
    if not storage.get_patient(patient_id):
        raise HTTPException(status_code=404, detail=f"Patient {patient_id} not found")
    raise HTTPException(
        status_code=400,
        detail=f"Cannot delete patient {patient_id}: patient has associated cases",
    )


@router.post("/cases/{case_id}/assign/{patient_id}", response_model=Case)
async def assign_case_to_patient(
    case_id: str, patient_id: str, storage: Storage = Depends(get_storage)
):
    """Assign a case to a patient."""
    if not storage.get_patient(patient_id):
        raise HTTPException(status_code=404, detail=f"Patient {patient_id} not found")
    case = storage.assign_case_to_patient(case_id, patient_id)
    if not case:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found")
    return case
