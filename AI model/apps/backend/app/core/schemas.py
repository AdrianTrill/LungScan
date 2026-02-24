"""Pydantic models for request/response schemas."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class Nodule(BaseModel):
    """Represents a detected lung nodule with position and malignancy score."""

    id: str = Field(..., description="Unique identifier for the nodule")
    x: int = Field(..., description="X coordinate (pixels) of nodule center")
    y: int = Field(..., description="Y coordinate (pixels) of nodule center")
    radius: int = Field(..., description="Radius of the nodule in pixels")
    malignancy_score: float = Field(
        ..., ge=0.0, le=1.0, description="Malignancy score between 0.0 and 1.0"
    )
    explanation: str = Field(..., description="Short explanation of the nodule characteristics")


class PatientCreate(BaseModel):
    """Request body for creating a patient."""

    first_name: str = Field(..., description="Patient's first name")
    last_name: str = Field(..., description="Patient's last name")
    date_of_birth: str = Field(..., description="Patient's date of birth (YYYY-MM-DD)")
    medical_record_number: str = Field(
        "", description="Medical record number (optional)"
    )


class UploadResult(BaseModel):
    """Response after uploading a scan file."""

    case_id: str = Field(..., description="Unique identifier for the case")
    filename: str = Field(..., description="Original filename of the uploaded scan")
    patient_id: str | None = Field(
        None, description="Patient identifier if assigned"
    )
    uploaded_at: datetime = Field(..., description="Timestamp when the file was uploaded")


class AnalyzeResult(BaseModel):
    """Response from the analysis endpoint with detected nodules."""

    case_id: str = Field(..., description="Case identifier")
    nodules: list[Nodule] = Field(..., description="List of detected nodules")
    summary: str = Field(..., description="Brief summary of the analysis")


class Patient(BaseModel):
    """Represents a patient."""

    id: str = Field(..., description="Unique patient identifier")
    first_name: str = Field(..., description="Patient's first name")
    last_name: str = Field(..., description="Patient's last name")
    date_of_birth: str = Field(..., description="Patient's date of birth (YYYY-MM-DD)")
    medical_record_number: str = Field(
        "", description="Medical record number (optional)"
    )
    created_at: datetime = Field(..., description="Patient creation timestamp")

    @property
    def full_name(self) -> str:
        """Get patient's full name."""
        return f"{self.first_name} {self.last_name}"


class Case(BaseModel):
    """Represents a medical case with scan and analysis status."""

    id: str = Field(..., description="Unique case identifier")
    filename: str = Field(..., description="Original filename")
    patient_id: str | None = Field(
        None, description="Patient identifier if assigned"
    )
    status: Literal["pending", "analyzed"] = Field(
        ..., description="Current status of the case"
    )
    created_at: datetime = Field(..., description="Case creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")


class CaseDetail(BaseModel):
    """Extended case information including analysis results."""

    case: Case = Field(..., description="Case information")
    patient: Patient | None = Field(None, description="Patient information if assigned")
    analysis_result: AnalyzeResult | None = Field(
        None, description="Analysis results if available"
    )
    notes: str | None = Field(None, description="Doctor's notes for this case")


class PatientDetail(BaseModel):
    """Patient information with associated cases."""

    patient: Patient = Field(..., description="Patient information")
    cases: list[Case] = Field(..., description="List of cases for this patient")


class ReportRequest(BaseModel):
    """Request body for generating a report."""

    notes: str = Field(..., description="Doctor's notes to include in the report")

