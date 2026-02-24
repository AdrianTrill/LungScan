/** TypeScript interfaces mirroring backend Pydantic schemas. */

export interface Nodule {
  id: string;
  x: number;
  y: number;
  radius: number;
  malignancy_score: number;
  explanation: string;
}

export interface UploadResult {
  case_id: string;
  filename: string;
  uploaded_at: string;
}

export interface AnalyzeResult {
  case_id: string;
  nodules: Nodule[];
  summary: string;
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

export interface PatientDetail {
  patient: Patient;
  cases: Case[];
}

export interface Case {
  id: string;
  filename: string;
  patient_id: string | null;
  status: "pending" | "analyzed";
  created_at: string;
  updated_at: string;
}

export interface CaseDetail {
  case: Case;
  patient: Patient | null;
  analysis_result: AnalyzeResult | null;
  notes: string | null;
}

export interface UploadResult {
  case_id: string;
  filename: string;
  patient_id: string | null;
  uploaded_at: string;
}

export interface ReportRequest {
  notes: string;
}

