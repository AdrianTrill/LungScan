/** Typed API client for backend routes with error handling. */

import {
  AnalyzeResult,
  Case,
  CaseDetail,
  Patient,
  PatientCreate,
  PatientDetail,
  ReportRequest,
  UploadResult,
} from "./types";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function fetchAPI<T>(
  endpoint: string,
  options?: RequestInit
): Promise<T> {
  const response = await fetch(`${API_URL}${endpoint}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({
      detail: `HTTP ${response.status}: ${response.statusText}`,
    }));
    throw new Error(error.detail || "API request failed");
  }

  return response.json();
}

async function uploadFile(
  file: File,
  patientId?: string
): Promise<UploadResult> {
  const formData = new FormData();
  formData.append("scan", file);
  if (patientId) {
    formData.append("patient_id", patientId);
  }

  const response = await fetch(`${API_URL}/api/upload`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({
      detail: `HTTP ${response.status}: ${response.statusText}`,
    }));
    throw new Error(error.detail || "Upload failed");
  }

  return response.json();
}

async function downloadFile(
  endpoint: string,
  filename: string
): Promise<void> {
  const response = await fetch(`${API_URL}${endpoint}`);
  if (!response.ok) {
    throw new Error("Download failed");
  }

  const blob = await response.blob();
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  window.URL.revokeObjectURL(url);
  document.body.removeChild(a);
}

export const api = {
  /** Upload a CT scan file. */
  uploadScan: (file: File, patientId?: string): Promise<UploadResult> =>
    uploadFile(file, patientId),

  /** Run analysis on a case. */
  analyzeCase: (caseId: string): Promise<AnalyzeResult> =>
    fetchAPI<AnalyzeResult>(`/api/analyze/${caseId}`, { method: "POST" }),

  /** Get all cases. */
  getCases: (): Promise<Case[]> => fetchAPI<Case[]>("/api/cases"),

  /** Get a single case with details. */
  getCase: (caseId: string): Promise<CaseDetail> =>
    fetchAPI<CaseDetail>(`/api/cases/${caseId}`),

  /** Delete a case. */
  deleteCase: (caseId: string): Promise<void> =>
    fetchAPI<void>(`/api/cases/${caseId}`, { method: "DELETE" }),

  /** Get all patients. */
  getPatients: (): Promise<Patient[]> =>
    fetchAPI<Patient[]>("/api/patients"),

  /** Get a single patient with details. */
  getPatient: (patientId: string): Promise<PatientDetail> =>
    fetchAPI<PatientDetail>(`/api/patients/${patientId}`),

  /** Create a new patient. */
  createPatient: (patient: PatientCreate): Promise<Patient> =>
    fetchAPI<Patient>("/api/patients", {
      method: "POST",
      body: JSON.stringify(patient),
    }),

  /** Delete a patient. */
  deletePatient: (patientId: string): Promise<void> =>
    fetchAPI<void>(`/api/patients/${patientId}`, { method: "DELETE" }),

  /** Assign a case to a patient. */
  assignCaseToPatient: (
    caseId: string,
    patientId: string
  ): Promise<Case> =>
    fetchAPI<Case>(`/api/cases/${caseId}/assign/${patientId}`, {
      method: "POST",
    }),

  /** Generate and download a report. */
  generateReport: async (caseId: string, notes: string): Promise<void> => {
    const request: ReportRequest = { notes };
    const response = await fetch(`${API_URL}/api/report/${caseId}`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(request),
    });

    if (!response.ok) {
      throw new Error("Report generation failed");
    }

    const contentDisposition = response.headers.get("Content-Disposition");
    const filename =
      contentDisposition?.match(/filename="(.+)"/)?.[1] ||
      `report_${caseId}.txt`;

    const blob = await response.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    document.body.removeChild(a);
  },
};

