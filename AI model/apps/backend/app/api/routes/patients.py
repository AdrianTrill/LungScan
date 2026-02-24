"""Patient management endpoints."""

from fastapi import APIRouter, HTTPException

from app.core.schemas import Patient, PatientCreate, PatientDetail
from app.core.utils import generate_case_id
from app.services.storage import storage

router = APIRouter()


@router.post("/patients", response_model=Patient, status_code=201)
async def create_patient(patient_data: PatientCreate):
    """Create a new patient.

    Args:
        patient_data: Patient information

    Returns:
        Created patient
    """
    patient_id = f"patient-{generate_case_id()[:8]}"
    patient = storage.create_patient(
        patient_id=patient_id,
        first_name=patient_data.first_name,
        last_name=patient_data.last_name,
        date_of_birth=patient_data.date_of_birth,
        medical_record_number=patient_data.medical_record_number,
    )
    return patient


@router.get("/patients", response_model=list[Patient])
async def list_patients():
    """Get all patients sorted by last name.

    Returns:
        List of Patient objects
    """
    return storage.get_all_patients()


@router.get("/patients/{patient_id}", response_model=PatientDetail)
async def get_patient(patient_id: str):
    """Get detailed information about a specific patient.

    Args:
        patient_id: Unique identifier for the patient

    Returns:
        PatientDetail with patient info and associated cases

    Raises:
        HTTPException: If patient is not found
    """
    patient_detail = storage.get_patient_detail(patient_id)
    if not patient_detail:
        raise HTTPException(status_code=404, detail=f"Patient {patient_id} not found")
    return patient_detail


@router.delete("/patients/{patient_id}")
async def delete_patient(patient_id: str):
    """Delete a patient (only if they have no cases).

    Args:
        patient_id: Unique identifier for the patient

    Returns:
        Success message

    Raises:
        HTTPException: If patient is not found or has cases
    """
    success = storage.delete_patient(patient_id)
    if not success:
        patient = storage.get_patient(patient_id)
        if not patient:
            raise HTTPException(
                status_code=404, detail=f"Patient {patient_id} not found"
            )
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete patient {patient_id}: patient has associated cases",
        )
    return {"message": f"Patient {patient_id} deleted successfully"}


@router.post("/cases/{case_id}/assign/{patient_id}")
async def assign_case_to_patient(case_id: str, patient_id: str):
    """Assign a case to a patient.
    
    Validates that the patient doesn't already have a case assigned.

    Args:
        case_id: Case identifier
        patient_id: Patient identifier

    Returns:
        Updated case

    Raises:
        HTTPException: If case or patient is not found, or patient already has a case
    """
    # Check if patient already has a case
    patient_detail = storage.get_patient_detail(patient_id)
    if not patient_detail:
        raise HTTPException(
            status_code=404, detail=f"Patient {patient_id} not found"
        )
    
    # Check if patient already has cases (excluding the current case being assigned)
    existing_cases = [c for c in patient_detail.cases if c.id != case_id]
    if existing_cases:
        raise HTTPException(
            status_code=400,
            detail=f"Patient {patient_detail.patient.first_name} {patient_detail.patient.last_name} already has {len(existing_cases)} case(s) assigned. Each patient can only have one case."
        )
    
    case = storage.assign_case_to_patient(case_id, patient_id)
    if not case:
        raise HTTPException(
            status_code=404, detail=f"Case {case_id} not found"
        )
    return case

