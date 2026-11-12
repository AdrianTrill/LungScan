/** Data types, mirroring the backend's Pydantic schemas (backend/app/core/schemas.py). */

export type Label =
  "adenocarcinoma" | "large_cell_carcinoma" | "normal" | "squamous_cell_carcinoma";

export interface Box {
  x: number;
  y: number;
  width: number;
  height: number;
}

/** Grad-CAM evidence for cancer on a size x size grid over `box`, in image pixels. */
export interface Heatmap {
  size: number;
  values: number[];
  box: Box;
}

/** A region where the Grad-CAM evidence for cancer peaks. */
export interface Region {
  id: string;
  x: number;
  y: number;
  radius: number;
  evidence: number;
  cells: number;
  explanation: string;
}

export interface ModelInfo {
  name: string;
  source: string;
  runtime: string;
}

export interface AnalyzeResult {
  case_id: string;
  cancer_probability: number;
  flagged: boolean;
  predicted_class: Label;
  subtype: Label | null;
  probabilities: Record<Label, number>;
  heatmap: Heatmap;
  regions: Region[];
  summary: string;
  model: ModelInfo;
  inference_ms: number;
  analyzed_at: string;
}

export interface Patient {
  id: string;
  first_name: string;
  last_name: string;
  date_of_birth: string;
  medical_record_number: string;
  created_at: string;
}

export interface PatientCreate {
  first_name: string;
  last_name: string;
  date_of_birth: string;
  medical_record_number?: string;
}

export interface Case {
  id: string;
  filename: string;
  patient_id: string | null;
  status: "pending" | "analyzed";
  created_at: string;
  updated_at: string;
  cancer_probability: number | null;
  flagged: boolean | null;
  dataset_label: Label | null;
}

export interface CaseDetail {
  case: Case;
  patient: Patient | null;
  analysis_result: AnalyzeResult | null;
  notes: string | null;
}

export interface PatientDetail {
  patient: Patient;
  cases: Case[];
}

export interface UploadResult {
  case_id: string;
  filename: string;
  patient_id: string | null;
  uploaded_at: string;
}
