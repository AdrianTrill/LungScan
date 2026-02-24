"""Persistent storage service for cases, analysis results, and notes.

Uses JSON files for persistence, with automatic save/load functionality.
"""

import json
import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path

from app.core.schemas import AnalyzeResult, Case, CaseDetail, Nodule, Patient, PatientDetail
from app.core.utils import generate_case_id

logger = logging.getLogger(__name__)

# Storage directory for JSON files
STORAGE_DIR = Path(__file__).parent.parent.parent / "data"
STORAGE_DIR.mkdir(exist_ok=True)

PATIENTS_FILE = STORAGE_DIR / "patients.json"
CASES_FILE = STORAGE_DIR / "cases.json"
RESULTS_FILE = STORAGE_DIR / "results.json"
NOTES_FILE = STORAGE_DIR / "notes.json"
IMAGE_PATHS_FILE = STORAGE_DIR / "image_paths.json"


class Storage:
    """Persistent storage for cases, analysis results, and notes."""

    def __init__(self):
        """Initialize storage and load existing data or seed with sample data."""
        self.cases: dict[str, Case] = {}
        self.results: dict[str, AnalyzeResult] = {}
        self.notes: dict[str, str] = {}
        self.patients: dict[str, Patient] = {}
        self.image_paths: dict[str, str] = {}  # case_id -> image_path
        
        # Load existing data from disk
        data_exists = self._load_from_disk()
        
        # Only seed if no data exists (first run)
        if not data_exists:
            logger.info("No existing data found, seeding with sample data")
            self._seed_data()
            self._save_to_disk()
        else:
            logger.info(f"Loaded {len(self.patients)} patients and {len(self.cases)} cases from disk")

    def _load_from_disk(self) -> bool:
        """Load data from JSON files. Returns True if data was loaded."""
        try:
            # Load patients
            if PATIENTS_FILE.exists():
                with open(PATIENTS_FILE, "r") as f:
                    patients_data = json.load(f)
                    for pid, pdata in patients_data.items():
                        pdata["created_at"] = datetime.fromisoformat(pdata["created_at"])
                        self.patients[pid] = Patient(**pdata)
            
            # Load cases
            if CASES_FILE.exists():
                with open(CASES_FILE, "r") as f:
                    cases_data = json.load(f)
                    for cid, cdata in cases_data.items():
                        cdata["created_at"] = datetime.fromisoformat(cdata["created_at"])
                        cdata["updated_at"] = datetime.fromisoformat(cdata["updated_at"])
                        self.cases[cid] = Case(**cdata)
            
            # Load results
            if RESULTS_FILE.exists():
                with open(RESULTS_FILE, "r") as f:
                    results_data = json.load(f)
                    for rid, rdata in results_data.items():
                        # Convert nodules to Nodule objects
                        nodules = [Nodule(**n) for n in rdata["nodules"]]
                        self.results[rid] = AnalyzeResult(
                            case_id=rdata["case_id"],
                            nodules=nodules,
                            summary=rdata["summary"]
                        )
            
            # Load notes
            if NOTES_FILE.exists():
                with open(NOTES_FILE, "r") as f:
                    self.notes = json.load(f)
            
            # Load image paths
            if IMAGE_PATHS_FILE.exists():
                with open(IMAGE_PATHS_FILE, "r") as f:
                    self.image_paths = json.load(f)
            
            return len(self.patients) > 0 or len(self.cases) > 0
        except Exception as e:
            logger.error(f"Error loading data from disk: {e}", exc_info=True)
            return False

    def _save_to_disk(self):
        """Save all data to JSON files."""
        try:
            # Save patients
            patients_data = {}
            for pid, patient in self.patients.items():
                patients_data[pid] = {
                    "id": patient.id,
                    "first_name": patient.first_name,
                    "last_name": patient.last_name,
                    "date_of_birth": patient.date_of_birth,
                    "medical_record_number": patient.medical_record_number,
                    "created_at": patient.created_at.isoformat(),
                }
            with open(PATIENTS_FILE, "w") as f:
                json.dump(patients_data, f, indent=2)
            
            # Save cases
            cases_data = {}
            for cid, case in self.cases.items():
                cases_data[cid] = {
                    "id": case.id,
                    "filename": case.filename,
                    "patient_id": case.patient_id,
                    "status": case.status,
                    "created_at": case.created_at.isoformat(),
                    "updated_at": case.updated_at.isoformat(),
                }
            with open(CASES_FILE, "w") as f:
                json.dump(cases_data, f, indent=2)
            
            # Save results
            results_data = {}
            for rid, result in self.results.items():
                results_data[rid] = {
                    "case_id": result.case_id,
                    "nodules": [
                        {
                            "id": n.id,
                            "x": n.x,
                            "y": n.y,
                            "radius": n.radius,
                            "malignancy_score": n.malignancy_score,
                            "explanation": n.explanation,
                        }
                        for n in result.nodules
                    ],
                    "summary": result.summary,
                }
            with open(RESULTS_FILE, "w") as f:
                json.dump(results_data, f, indent=2)
            
            # Save notes
            with open(NOTES_FILE, "w") as f:
                json.dump(self.notes, f, indent=2)
            
            # Save image paths
            with open(IMAGE_PATHS_FILE, "w") as f:
                json.dump(self.image_paths, f, indent=2)
            
            logger.debug("Data saved to disk")
        except Exception as e:
            logger.error(f"Error saving data to disk: {e}", exc_info=True)

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
        self._save_to_disk()
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
                    path = Path(image_path)
                    if path.exists():
                        path.unlink()
                except Exception:
                    pass  # Ignore errors when deleting files
                del self.image_paths[case_id]
            self._save_to_disk()
            return True
        return False

    def update_case_status(self, case_id: str, status: str) -> Case | None:
        """Update the status of a case."""
        if case_id not in self.cases:
            return None
        case = self.cases[case_id]
        case.status = status
        case.updated_at = datetime.now(timezone.utc)
        self._save_to_disk()
        return case

    def save_analysis_result(self, result: AnalyzeResult) -> None:
        """Store an analysis result."""
        self.results[result.case_id] = result
        self._save_to_disk()

    def get_analysis_result(self, case_id: str) -> AnalyzeResult | None:
        """Retrieve analysis result for a case."""
        return self.results.get(case_id)

    def save_notes(self, case_id: str, notes: str) -> None:
        """Save notes for a case."""
        self.notes[case_id] = notes
        self._save_to_disk()

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
        self._save_to_disk()
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
            self._save_to_disk()
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
        self._save_to_disk()
        return case

    def save_image_path(self, case_id: str, image_path: str) -> None:
        """Save the image path for a case."""
        self.image_paths[case_id] = image_path
        self._save_to_disk()

    def get_image_path(self, case_id: str) -> str | None:
        """Get the image path for a case."""
        return self.image_paths.get(case_id)

    def replace_case_image(self, case_id: str, new_image_path: str, new_filename: str) -> Case | None:
        """Replace the image for an existing case.
        
        Args:
            case_id: The case ID to update
            new_image_path: Path to the new image file
            new_filename: New display filename for the case
            
        Returns:
            Updated Case object or None if case not found
        """
        if case_id not in self.cases:
            return None
        
        case = self.cases[case_id]
        
        # Delete old image file if it exists
        old_image_path = self.image_paths.get(case_id)
        if old_image_path:
            try:
                path = Path(old_image_path)
                if path.exists() and path != Path(new_image_path):
                    path.unlink()
            except Exception:
                pass  # Ignore errors when deleting old file
        
        # Update image path
        self.image_paths[case_id] = new_image_path
        
        # Update case filename and timestamp
        case.filename = new_filename
        case.updated_at = datetime.now(timezone.utc)
        
        # Reset case status to pending and clear analysis results
        case.status = "pending"
        if case_id in self.results:
            del self.results[case_id]
        if case_id in self.notes:
            # Optionally keep notes, or delete them
            # For now, we'll keep notes as they might still be relevant
            pass
        
        self._save_to_disk()
        return case

    def _seed_data(self):
        """Seed the storage with sample data for development (only called on first run)."""
        from app.core.utils import generate_nodule_id

        # Create sample patients with fixed IDs (only if they don't exist)
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
        ]

        for patient_data in patients_data:
            patient_id = patient_data.pop("patient_id")
            if patient_id not in self.patients:
                now = datetime.now(timezone.utc)
                patient = Patient(
                    id=patient_id,
                    first_name=patient_data["first_name"],
                    last_name=patient_data["last_name"],
                    date_of_birth=patient_data["date_of_birth"],
                    medical_record_number=patient_data["medical_record_number"],
                    created_at=now,
                )
                self.patients[patient_id] = patient

        # Create sample cases using images from uploads folder (case-001.png, case-002.png, etc.)
        now = datetime.now(timezone.utc)
        uploads_dir = Path(__file__).parent.parent.parent / "uploads"
        uploads_dir.mkdir(exist_ok=True)
        
        cases_data = [
            {
                "id": "case-001",
                "filename": f"John_Smith_CT_Scan_{now.strftime('%Y%m%d')}.png",
                "patient_id": "patient-001",
                "status": "analyzed",
                "created_at": now,
                "updated_at": now,
            },
            {
                "id": "case-002",
                "filename": f"Sarah_Johnson_CT_Scan_{now.strftime('%Y%m%d')}.png",
                "patient_id": "patient-002",
                "status": "analyzed",
                "created_at": now,
                "updated_at": now,
            },
            {
                "id": "case-003",
                "filename": f"Michael_Williams_CT_Scan_{now.strftime('%Y%m%d')}.png",
                "patient_id": "patient-003",
                "status": "analyzed",
                "created_at": now,
                "updated_at": now,
            },
            {
                "id": "case-004",
                "filename": f"Emily_Brown_CT_Scan_{now.strftime('%Y%m%d')}.png",
                "patient_id": "patient-004",
                "status": "analyzed",
                "created_at": now,
                "updated_at": now,
            },
            {
                "id": "case-005",
                "filename": f"Robert_Davis_CT_Scan_{now.strftime('%Y%m%d')}.png",
                "patient_id": "patient-005",
                "status": "analyzed",
                "created_at": now,
                "updated_at": now,
            },
        ]

        for case_data in cases_data:
            case_id = case_data["id"]
            
            # Only create if case doesn't exist
            if case_id in self.cases:
                continue
            
            # Use existing image from uploads folder (case-001.png, case-002.png, etc.)
            image_path = uploads_dir / f"{case_id}.png"
            
            if image_path.exists():
                # Use the existing image from uploads folder
                self.image_paths[case_id] = str(image_path)
                logger.info(f"Using existing image for {case_id}: {image_path}")
            else:
                # Fallback: try to copy from static/images if uploads image doesn't exist
                static_images_dir = Path(__file__).parent.parent.parent / "static" / "images"
                sample_images = sorted(list(static_images_dir.glob("*.png")))
                case_index = int(case_id.split("-")[1]) - 1  # Extract number from case-001 -> 0
                
                if case_index < len(sample_images):
                    source_image = sample_images[case_index]
                    shutil.copy2(source_image, image_path)
                    self.image_paths[case_id] = str(image_path)
                    logger.info(f"Copied image from static/images for {case_id}: {image_path}")
                else:
                    logger.warning(f"No image found for {case_id}, skipping image path")
            
            self.cases[case_id] = Case(**case_data)

        # Run real AI analysis on seed cases (only if they don't exist)
        analyzed_cases = ["case-001", "case-002", "case-003", "case-004", "case-005"]
        
        for case_id in analyzed_cases:
            # Skip if result already exists
            if case_id in self.results:
                continue
            
            # Get image path for this case
            image_path = self.image_paths.get(case_id)
            if not image_path or not Path(image_path).exists():
                logger.warning(f"No image found for case {case_id}, skipping analysis")
                continue
            
            # Run real AI analysis on the image
            try:
                from app.services.analysis import analyze_image
                logger.info(f"Running AI analysis on seed case {case_id}")
                analysis_result = analyze_image(image_path=Path(image_path), case_id=case_id)
                self.results[case_id] = analysis_result
                
                # Add sample notes for first case if notes don't exist
                if case_id == "case-001" and case_id not in self.notes:
                    self.notes[case_id] = "Patient requires follow-up CT scan in 3 months. Recommended biopsy for nodule with highest malignancy score."
                    
            except Exception as e:
                logger.error(f"Failed to run AI analysis on seed case {case_id}: {e}", exc_info=True)
                # If AI analysis fails, create a simple "no nodules detected" result
                analysis_result = AnalyzeResult(
                    case_id=case_id,
                    nodules=[],
                    summary="Analysis attempted but encountered an error. Please re-analyze this case."
                )
                self.results[case_id] = analysis_result


# Global storage instance
storage = Storage()
