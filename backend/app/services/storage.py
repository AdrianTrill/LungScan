"""Persistent storage for patients, cases, analysis results, and notes.

Everything is kept in memory and written to JSON files in the data directory after
each change. Uploaded images live in the upload directory, named by case ID.
"""

from __future__ import annotations

import json
import logging
import shutil
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

from pydantic import ValidationError

from app.core.schemas import AnalyzeResult, Case, CaseDetail, Patient, PatientDetail

logger = logging.getLogger(__name__)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Storage:
    """Patients, cases, results, notes, and images, persisted as JSON files."""

    def __init__(
        self,
        data_dir: Path,
        upload_dir: Path,
        samples_dir: Path | None = None,
        seed: bool = False,
    ):
        self.data_dir = Path(data_dir)
        self.upload_dir = Path(upload_dir)
        self.samples_dir = Path(samples_dir) if samples_dir else None
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

        self.patients: dict[str, Patient] = {}
        self.cases: dict[str, Case] = {}
        self.results: dict[str, AnalyzeResult] = {}
        self.notes: dict[str, str] = {}
        self.images: dict[str, str] = {}

        if self._load():
            logger.info("Loaded %d patients and %d cases", len(self.patients), len(self.cases))
        elif seed and self.samples_dir:
            self.seed_samples()

    # Persistence

    def _file(self, name: str) -> Path:
        return self.data_dir / f"{name}.json"

    def _load(self) -> bool:
        def read(name: str) -> dict:
            path = self._file(name)
            return json.loads(path.read_text()) if path.exists() else {}

        try:
            self.patients = {k: Patient.model_validate(v) for k, v in read("patients").items()}
            self.cases = {k: Case.model_validate(v) for k, v in read("cases").items()}
            self.notes = read("notes")
            self.images = read("images")
        except (ValidationError, json.JSONDecodeError) as error:
            logger.error("Ignoring unreadable data in %s: %s", self.data_dir, error)
            self.patients, self.cases, self.notes, self.images = {}, {}, {}, {}
            return False

        for case_id, value in read("results").items():
            try:
                self.results[case_id] = AnalyzeResult.model_validate(value)
            except ValidationError:
                # A result from an older version of the analysis: the case is read again.
                logger.warning("Dropping an outdated analysis result for case %s", case_id)
                if case_id in self.cases:
                    self.cases[case_id] = self.cases[case_id].model_copy(
                        update={"status": "pending", "cancer_probability": None, "flagged": None}
                    )
        return bool(self.patients or self.cases)

    def _save(self) -> None:
        def write(name: str, data: dict) -> None:
            path = self._file(name)
            tmp = path.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(data, indent=2))
            tmp.replace(path)

        write("patients", {k: v.model_dump(mode="json") for k, v in self.patients.items()})
        write("cases", {k: v.model_dump(mode="json") for k, v in self.cases.items()})
        write("results", {k: v.model_dump(mode="json") for k, v in self.results.items()})
        write("notes", self.notes)
        write("images", self.images)

    # Cases

    def create_case(
        self,
        case_id: str,
        filename: str,
        patient_id: str | None = None,
        dataset_label: str | None = None,
        created_at: datetime | None = None,
    ) -> Case:
        with self._lock:
            now = created_at or utcnow()
            case = Case(
                id=case_id,
                filename=filename,
                patient_id=patient_id,
                status="pending",
                created_at=now,
                updated_at=now,
                dataset_label=dataset_label,
            )
            self.cases[case_id] = case
            self._save()
            return case

    def get_case(self, case_id: str) -> Case | None:
        return self.cases.get(case_id)

    def get_all_cases(self) -> list[Case]:
        """All cases, most recently updated first."""
        return sorted(self.cases.values(), key=lambda c: c.updated_at, reverse=True)

    def delete_case(self, case_id: str) -> bool:
        with self._lock:
            if case_id not in self.cases:
                return False
            del self.cases[case_id]
            self.results.pop(case_id, None)
            self.notes.pop(case_id, None)
            image = self.image_path(case_id)
            if image and image.is_relative_to(self.upload_dir):
                image.unlink(missing_ok=True)
            self.images.pop(case_id, None)
            self._save()
            return True

    def save_analysis_result(self, result: AnalyzeResult) -> Case | None:
        """Store a result and mark its case as analyzed."""
        with self._lock:
            case = self.cases.get(result.case_id)
            if case is None:
                return None
            self.results[result.case_id] = result
            case = case.model_copy(
                update={
                    "status": "analyzed",
                    "cancer_probability": result.cancer_probability,
                    "flagged": result.flagged,
                    "updated_at": utcnow(),
                }
            )
            self.cases[case.id] = case
            self._save()
            return case

    def get_analysis_result(self, case_id: str) -> AnalyzeResult | None:
        return self.results.get(case_id)

    def save_notes(self, case_id: str, notes: str) -> None:
        with self._lock:
            self.notes[case_id] = notes
            self._save()

    def get_notes(self, case_id: str) -> str | None:
        return self.notes.get(case_id)

    def get_case_detail(self, case_id: str) -> CaseDetail | None:
        case = self.get_case(case_id)
        if not case:
            return None
        patient = self.get_patient(case.patient_id) if case.patient_id else None
        return CaseDetail(
            case=case,
            patient=patient,
            analysis_result=self.get_analysis_result(case_id),
            notes=self.get_notes(case_id),
        )

    def assign_case_to_patient(self, case_id: str, patient_id: str) -> Case | None:
        with self._lock:
            if case_id not in self.cases or patient_id not in self.patients:
                return None
            case = self.cases[case_id].model_copy(
                update={"patient_id": patient_id, "updated_at": utcnow()}
            )
            self.cases[case_id] = case
            self._save()
            return case

    # Images

    def save_image(self, case_id: str, content: bytes, extension: str) -> Path:
        """Write a case's image to the upload directory, replacing any previous one."""
        with self._lock:
            old = self.image_path(case_id)
            name = f"{case_id}{extension.lower()}"
            path = self.upload_dir / name
            path.write_bytes(content)
            if old and old != path and old.is_relative_to(self.upload_dir):
                old.unlink(missing_ok=True)
            self.images[case_id] = name
            self._save()
            return path

    def image_path(self, case_id: str) -> Path | None:
        name = self.images.get(case_id)
        if not name:
            return None
        path = Path(name)
        return path if path.is_absolute() else self.upload_dir / path

    def replace_case_image(
        self, case_id: str, content: bytes, extension: str, filename: str
    ) -> Case | None:
        """Swap a case's image: the case goes back to pending, its notes are kept."""
        with self._lock:
            if case_id not in self.cases:
                return None
            self.save_image(case_id, content, extension)
            self.results.pop(case_id, None)
            case = self.cases[case_id].model_copy(
                update={
                    "filename": filename,
                    "status": "pending",
                    "cancer_probability": None,
                    "flagged": None,
                    "dataset_label": None,
                    "updated_at": utcnow(),
                }
            )
            self.cases[case_id] = case
            self._save()
            return case

    # Patients

    def create_patient(
        self,
        patient_id: str,
        first_name: str,
        last_name: str,
        date_of_birth: str,
        medical_record_number: str = "",
        created_at: datetime | None = None,
    ) -> Patient:
        with self._lock:
            patient = Patient(
                id=patient_id,
                first_name=first_name,
                last_name=last_name,
                date_of_birth=date_of_birth,
                medical_record_number=medical_record_number,
                created_at=created_at or utcnow(),
            )
            self.patients[patient_id] = patient
            self._save()
            return patient

    def get_patient(self, patient_id: str) -> Patient | None:
        return self.patients.get(patient_id)

    def get_all_patients(self) -> list[Patient]:
        """All patients, sorted by last name."""
        return sorted(self.patients.values(), key=lambda p: (p.last_name, p.first_name))

    def delete_patient(self, patient_id: str) -> bool:
        """Delete a patient, as long as no case belongs to them."""
        with self._lock:
            if any(c.patient_id == patient_id for c in self.cases.values()):
                return False
            if self.patients.pop(patient_id, None) is None:
                return False
            self._save()
            return True

    def get_patient_detail(self, patient_id: str) -> PatientDetail | None:
        patient = self.get_patient(patient_id)
        if not patient:
            return None
        cases = [c for c in self.cases.values() if c.patient_id == patient_id]
        cases.sort(key=lambda c: c.updated_at, reverse=True)
        return PatientDetail(patient=patient, cases=cases)

    # Samples

    def seed_samples(self) -> None:
        """Add the demo patients and the sample slices, with the model's precomputed reads."""
        manifest_path = self.samples_dir / "samples.json"
        if not manifest_path.exists():
            logger.warning("No samples at %s; starting empty", manifest_path)
            return
        manifest = json.loads(manifest_path.read_text())
        now = utcnow()
        with self._lock:
            for i, p in enumerate(manifest["patients"]):
                self.patients[p["id"]] = Patient(
                    id=p["id"],
                    first_name=p["first_name"],
                    last_name=p["last_name"],
                    date_of_birth=p["date_of_birth"],
                    medical_record_number=p["medical_record_number"],
                    created_at=now - timedelta(days=30 - i),
                )
            for i, s in enumerate(manifest["cases"]):
                when = now - timedelta(hours=6 * (len(manifest["cases"]) - i))
                source = self.samples_dir / s["image"]
                name = f"{s['id']}{source.suffix}"
                shutil.copyfile(source, self.upload_dir / name)
                self.images[s["id"]] = name
                result = AnalyzeResult.model_validate(
                    {**s["result"], "case_id": s["id"], "analyzed_at": when.isoformat()}
                )
                self.cases[s["id"]] = Case(
                    id=s["id"],
                    filename=s["filename"],
                    patient_id=s["patient_id"],
                    status="analyzed",
                    created_at=when,
                    updated_at=when,
                    cancer_probability=result.cancer_probability,
                    flagged=result.flagged,
                    dataset_label=s["label"],
                )
                self.results[s["id"]] = result
                if s.get("notes"):
                    self.notes[s["id"]] = s["notes"]
            self._save()
        logger.info("Seeded %d sample cases", len(manifest["cases"]))
