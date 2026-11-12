"""Pydantic models for request/response schemas."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class Box(BaseModel):
    """A rectangle in the original image, in pixels."""

    x: float
    y: float
    width: float
    height: float


class Heatmap(BaseModel):
    """Grad-CAM evidence for cancer on a size x size grid over `box`."""

    size: int = Field(..., description="The grid is size x size cells")
    values: list[float] = Field(
        ..., description="Row-major evidence per cell, 0 to 1, scaled by the cancer probability"
    )
    box: Box = Field(..., description="The part of the image the model sees (its center crop)")


class Region(BaseModel):
    """A region where the Grad-CAM evidence for cancer peaks."""

    id: str = Field(..., description="Identifier, unique within one result")
    x: int = Field(..., description="X coordinate (pixels) of the region's center")
    y: int = Field(..., description="Y coordinate (pixels) of the region's center")
    radius: int = Field(..., description="Approximate radius of the region in pixels")
    evidence: float = Field(..., ge=0.0, le=1.0, description="Peak evidence, 0 to 1")
    cells: int = Field(..., description="Grid cells the region covers")
    explanation: str = Field(..., description="Short description of the region")


class ModelInfo(BaseModel):
    """Which model produced a result, and where it ran."""

    name: str
    source: str
    runtime: str


class PatientCreate(BaseModel):
    """Request body for creating a patient."""

    first_name: str = Field(..., min_length=1, description="Patient's first name")
    last_name: str = Field(..., min_length=1, description="Patient's last name")
    date_of_birth: str = Field(..., description="Patient's date of birth (YYYY-MM-DD)")
    medical_record_number: str = Field("", description="Medical record number (optional)")


class UploadResult(BaseModel):
    """Response after uploading a scan file."""

    case_id: str = Field(..., description="Unique identifier for the case")
    filename: str = Field(..., description="Display filename of the uploaded scan")
    patient_id: str | None = Field(None, description="Patient identifier if assigned")
    uploaded_at: datetime = Field(..., description="Timestamp when the file was uploaded")


class AnalyzeResult(BaseModel):
    """The model's read of one CT slice."""

    case_id: str = Field(..., description="Case identifier")
    cancer_probability: float = Field(
        ..., ge=0.0, le=1.0, description="Probability of any of the three cancer classes"
    )
    flagged: bool = Field(..., description="True when the cancer probability is at least 0.5")
    predicted_class: str = Field(..., description="Most probable of the four classes")
    subtype: str | None = Field(None, description="Most probable cancer class, when flagged")
    probabilities: dict[str, float] = Field(..., description="Probability of each class")
    heatmap: Heatmap
    regions: list[Region] = Field(..., description="Where the cancer evidence peaks")
    summary: str = Field(..., description="One-paragraph summary of the read")
    model: ModelInfo
    inference_ms: float = Field(..., description="Time spent in the network, in milliseconds")
    analyzed_at: datetime


class Patient(BaseModel):
    """Represents a patient."""

    id: str = Field(..., description="Unique patient identifier")
    first_name: str = Field(..., description="Patient's first name")
    last_name: str = Field(..., description="Patient's last name")
    date_of_birth: str = Field(..., description="Patient's date of birth (YYYY-MM-DD)")
    medical_record_number: str = Field("", description="Medical record number (optional)")
    created_at: datetime = Field(..., description="Patient creation timestamp")


class Case(BaseModel):
    """A CT slice to read, with the headline of its analysis."""

    id: str = Field(..., description="Unique case identifier")
    filename: str = Field(..., description="Display filename")
    patient_id: str | None = Field(None, description="Patient identifier if assigned")
    status: Literal["pending", "analyzed"] = Field(..., description="Current status of the case")
    created_at: datetime = Field(..., description="Case creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    cancer_probability: float | None = Field(
        None, description="Cancer probability of the latest analysis"
    )
    flagged: bool | None = Field(None, description="Whether the latest analysis flagged cancer")
    dataset_label: str | None = Field(
        None, description="Ground-truth class, for the sample slices from the test split"
    )


class CaseDetail(BaseModel):
    """Extended case information including analysis results."""

    case: Case = Field(..., description="Case information")
    patient: Patient | None = Field(None, description="Patient information if assigned")
    analysis_result: AnalyzeResult | None = Field(None, description="Analysis results if available")
    notes: str | None = Field(None, description="Doctor's notes for this case")


class PatientDetail(BaseModel):
    """Patient information with associated cases."""

    patient: Patient = Field(..., description="Patient information")
    cases: list[Case] = Field(..., description="List of cases for this patient")


class NotesUpdate(BaseModel):
    """Request body for saving a case's notes."""

    notes: str = Field(..., description="Doctor's notes for the case")


class ReportRequest(BaseModel):
    """Request body for generating a report."""

    notes: str = Field(..., description="Doctor's notes to include in the report")
