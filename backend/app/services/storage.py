"""In-memory storage service for cases, analysis results, and notes.

This is a simple in-memory implementation that can be swapped out for
a database or file-based storage in the future.
"""

from datetime import datetime, timezone

from app.core.schemas import AnalyzeResult, Case, CaseDetail, Patient, PatientDetail
from app.core.utils import generate_case_id


class Storage:
    """In-memory storage for cases, analysis results, and notes."""

    def __init__(self):
        """Initialize empty storage dictionaries."""
        self.cases: dict[str, Case] = {}
        self.results: dict[str, AnalyzeResult] = {}
        self.notes: dict[str, str] = {}
        self.patients: dict[str, Patient] = {}
        self.image_paths: dict[str, str] = {}  # case_id -> image_path
        self._seed_data()

    def create_case(
        self, case_id: str, filename: str, patient_id: str | None = None
    ) -> Case:
        """Create a new case and store it."""
        now = datetime.now(timezone.utc)
        case = Case(
            id=case_id,
            filename=filename,
            patient_id=patient_id,
            status="pending",
            created_at=now,
            updated_at=now,
        )
        self.cases[case_id] = case
        return case

    def get_case(self, case_id: str) -> Case | None:
        """Retrieve a case by ID."""
        return self.cases.get(case_id)

    def get_all_cases(self) -> list[Case]:
        """Get all cases sorted by updated_at (most recent first)."""
        return sorted(
            list(self.cases.values()), key=lambda c: c.updated_at, reverse=True
        )

    def delete_case(self, case_id: str) -> bool:
        """Delete a case and its associated data."""
        if case_id in self.cases:
            del self.cases[case_id]
            if case_id in self.results:
                del self.results[case_id]
            if case_id in self.notes:
                del self.notes[case_id]
            # Delete associated image file if it exists
            if case_id in self.image_paths:
                image_path = self.image_paths[case_id]
                try:
                    from pathlib import Path
                    path = Path(image_path)
                    if path.exists():
                        path.unlink()
                except Exception:
                    pass  # Ignore errors when deleting files
                del self.image_paths[case_id]
            return True
        return False

    def update_case_status(self, case_id: str, status: str) -> Case | None:
        """Update the status of a case."""
        if case_id not in self.cases:
            return None
        case = self.cases[case_id]
        case.status = status
        case.updated_at = datetime.now(timezone.utc)
        return case

    def save_analysis_result(self, result: AnalyzeResult) -> None:
        """Store an analysis result."""
        self.results[result.case_id] = result

    def get_analysis_result(self, case_id: str) -> AnalyzeResult | None:
        """Retrieve analysis result for a case."""
        return self.results.get(case_id)

    def save_notes(self, case_id: str, notes: str) -> None:
        """Save notes for a case."""
        self.notes[case_id] = notes

    def get_notes(self, case_id: str) -> str | None:
        """Retrieve notes for a case."""
        return self.notes.get(case_id)

    def get_case_detail(self, case_id: str) -> CaseDetail | None:
        """Get complete case details including analysis and notes."""
        case = self.get_case(case_id)
        if not case:
            return None
        patient = None
        if case.patient_id:
            patient = self.get_patient(case.patient_id)
        return CaseDetail(
            case=case,
            patient=patient,
            analysis_result=self.get_analysis_result(case_id),
            notes=self.get_notes(case_id),
        )

    def create_patient(
        self,
        patient_id: str,
        first_name: str,
        last_name: str,
        date_of_birth: str,
        medical_record_number: str = "",
    ) -> Patient:
        """Create a new patient and store it."""
        now = datetime.now(timezone.utc)
        patient = Patient(
            id=patient_id,
            first_name=first_name,
            last_name=last_name,
            date_of_birth=date_of_birth,
            medical_record_number=medical_record_number,
            created_at=now,
        )
        self.patients[patient_id] = patient
        return patient

    def get_patient(self, patient_id: str) -> Patient | None:
        """Retrieve a patient by ID."""
        return self.patients.get(patient_id)

    def get_all_patients(self) -> list[Patient]:
        """Get all patients sorted by last name."""
        return sorted(
            list(self.patients.values()),
            key=lambda p: (p.last_name, p.first_name),
        )

    def delete_patient(self, patient_id: str) -> bool:
        """Delete a patient (only if they have no cases)."""
        # Check if patient has any cases
        has_cases = any(c.patient_id == patient_id for c in self.cases.values())
        if has_cases:
            return False
        if patient_id in self.patients:
            del self.patients[patient_id]
            return True
        return False

    def get_patient_detail(self, patient_id: str) -> PatientDetail | None:
        """Get patient details with associated cases."""
        patient = self.get_patient(patient_id)
        if not patient:
            return None
        cases = [c for c in self.cases.values() if c.patient_id == patient_id]
        cases = sorted(cases, key=lambda c: c.updated_at, reverse=True)
        return PatientDetail(patient=patient, cases=cases)

    def assign_case_to_patient(self, case_id: str, patient_id: str) -> Case | None:
        """Assign a case to a patient."""
        if case_id not in self.cases:
            return None
        if patient_id not in self.patients:
            return None
        case = self.cases[case_id]
        case.patient_id = patient_id
        case.updated_at = datetime.now(timezone.utc)
        return case

    def save_image_path(self, case_id: str, image_path: str) -> None:
        """Save the image path for a case."""
        self.image_paths[case_id] = image_path

    def get_image_path(self, case_id: str) -> str | None:
        """Get the image path for a case."""
        return self.image_paths.get(case_id)

    def _seed_data(self):
        """Seed the storage with sample data for development."""
        from app.core.schemas import AnalyzeResult, Nodule
        from app.core.utils import generate_nodule_id

        # Create sample patients with fixed IDs
        patients_data = [
            {
                "patient_id": "patient-001",
                "first_name": "John",
                "last_name": "Smith",
                "date_of_birth": "1975-03-15",
                "medical_record_number": "MRN-2024-001",
            },
            {
                "patient_id": "patient-002",
                "first_name": "Sarah",
                "last_name": "Johnson",
                "date_of_birth": "1982-07-22",
                "medical_record_number": "MRN-2024-002",
            },
            {
                "patient_id": "patient-003",
                "first_name": "Michael",
                "last_name": "Williams",
                "date_of_birth": "1968-11-08",
                "medical_record_number": "MRN-2024-003",
            },
            {
                "patient_id": "patient-004",
                "first_name": "Emily",
                "last_name": "Brown",
                "date_of_birth": "1990-05-30",
                "medical_record_number": "MRN-2024-004",
            },
            {
                "patient_id": "patient-005",
                "first_name": "Robert",
                "last_name": "Davis",
                "date_of_birth": "1955-12-10",
                "medical_record_number": "MRN-2024-005",
            },
            {
                "patient_id": "patient-006",
                "first_name": "Maria",
                "last_name": "Garcia",
                "date_of_birth": "1988-04-18",
                "medical_record_number": "MRN-2024-006",
            },
        ]

        for patient_data in patients_data:
            patient_id = patient_data.pop("patient_id")
            self.create_patient(
                patient_id=patient_id,
                first_name=patient_data["first_name"],
                last_name=patient_data["last_name"],
                date_of_birth=patient_data["date_of_birth"],
                medical_record_number=patient_data["medical_record_number"],
            )

        # Create sample cases with more variety
        now = datetime.now(timezone.utc)
        cases_data = [
            {
                "id": "case-001",
                "filename": "CT_Scan_John_Smith_2024-01-15.dcm",
                "patient_id": "patient-001",
                "status": "analyzed",
                "created_at": now,
                "updated_at": now,
            },
            {
                "id": "case-002",
                "filename": "CT_Scan_Sarah_Johnson_2024-01-20.dcm",
                "patient_id": "patient-002",
                "status": "pending",
                "created_at": now,
                "updated_at": now,
            },
            {
                "id": "case-003",
                "filename": "CT_Scan_Michael_Williams_2024-01-25.dcm",
                "patient_id": "patient-003",
                "status": "analyzed",
                "created_at": now,
                "updated_at": now,
            },
            {
                "id": "case-004",
                "filename": "CT_Scan_Emily_Brown_2024-02-01.dcm",
                "patient_id": "patient-004",
                "status": "analyzed",
                "created_at": now,
                "updated_at": now,
            },
            {
                "id": "case-005",
                "filename": "CT_Scan_Robert_Davis_2024-02-05.dcm",
                "patient_id": "patient-005",
                "status": "pending",
                "created_at": now,
                "updated_at": now,
            },
            {
                "id": "case-006",
                "filename": "CT_Scan_Maria_Garcia_2024-02-10.dcm",
                "patient_id": "patient-006",
                "status": "analyzed",
                "created_at": now,
                "updated_at": now,
            },
            {
                "id": "case-007",
                "filename": "CT_Scan_Unassigned_2024-02-15.dcm",
                "patient_id": None,
                "status": "pending",
                "created_at": now,
                "updated_at": now,
            },
            {
                "id": "case-008",
                "filename": "CT_Scan_John_Smith_FollowUp_2024-02-20.dcm",
                "patient_id": "patient-001",
                "status": "analyzed",
                "created_at": now,
                "updated_at": now,
            },
        ]

        for case_data in cases_data:
            self.cases[case_data["id"]] = Case(**case_data)

        # Create mock analysis results for analyzed cases
        analyzed_cases = ["case-001", "case-003", "case-004", "case-006", "case-008"]
        
        for case_id in analyzed_cases:
            # Create deterministic mock nodules
            nodules = []
            if case_id == "case-001":
                nodules = [
                    Nodule(
                        id=generate_nodule_id(),
                        x=150,
                        y=200,
                        radius=12,
                        malignancy_score=0.75,
                        explanation="Irregular nodule with spiculated borders, moderate suspicion (malignancy risk: high)",
                    ),
                    Nodule(
                        id=generate_nodule_id(),
                        x=350,
                        y=280,
                        radius=8,
                        malignancy_score=0.45,
                        explanation="Small rounded opacity with smooth margins, likely benign (malignancy risk: moderate)",
                    ),
                ]
            elif case_id == "case-003":
                nodules = [
                    Nodule(
                        id=generate_nodule_id(),
                        x=220,
                        y=180,
                        radius=15,
                        malignancy_score=0.82,
                        explanation="Central nodule with cavitation, high suspicion for malignancy (malignancy risk: very high)",
                    ),
                    Nodule(
                        id=generate_nodule_id(),
                        x=400,
                        y=320,
                        radius=10,
                        malignancy_score=0.35,
                        explanation="Ground-glass opacity with mixed density, requires follow-up (malignancy risk: moderate)",
                    ),
                    Nodule(
                        id=generate_nodule_id(),
                        x=180,
                        y=400,
                        radius=6,
                        malignancy_score=0.25,
                        explanation="Small nodule with halo sign, inflammatory process possible (malignancy risk: low)",
                    ),
                ]
            elif case_id == "case-004":
                nodules = [
                    Nodule(
                        id=generate_nodule_id(),
                        x=280,
                        y=250,
                        radius=18,
                        malignancy_score=0.68,
                        explanation="Partially solid nodule with irregular margins, moderate concern (malignancy risk: high)",
                    ),
                ]
            elif case_id == "case-006":
                nodules = [
                    Nodule(
                        id=generate_nodule_id(),
                        x=320,
                        y=220,
                        radius=9,
                        malignancy_score=0.52,
                        explanation="Solid nodule with well-defined edges, low malignancy risk (malignancy risk: moderate)",
                    ),
                    Nodule(
                        id=generate_nodule_id(),
                        x=150,
                        y=350,
                        radius=11,
                        malignancy_score=0.41,
                        explanation="Subpleural nodule with calcifications, likely benign (malignancy risk: moderate)",
                    ),
                ]
            elif case_id == "case-008":
                nodules = [
                    Nodule(
                        id=generate_nodule_id(),
                        x=250,
                        y=200,
                        radius=14,
                        malignancy_score=0.71,
                        explanation="Follow-up scan shows nodule growth, increased suspicion (malignancy risk: high)",
                    ),
                ]

            if nodules:
                summary = f"Analysis complete: {len(nodules)} nodule(s) detected. Average malignancy score: {sum(n.malignancy_score for n in nodules) / len(nodules):.3f}. {sum(1 for n in nodules if n.malignancy_score >= 0.6)} nodule(s) with high suspicion (≥0.6). Review recommended for all detected nodules."
                analysis_result = AnalyzeResult(
                    case_id=case_id, nodules=nodules, summary=summary
                )
                self.save_analysis_result(analysis_result)
                # Add sample notes
                if case_id in ["case-001", "case-003"]:
                    self.save_notes(case_id, "Patient requires follow-up CT scan in 3 months. Recommended biopsy for nodule with highest malignancy score.")
                elif case_id == "case-008":
                    self.save_notes(case_id, "Follow-up scan shows progression. Recommend immediate consultation with oncology team.")


# Global storage instance
storage = Storage()

