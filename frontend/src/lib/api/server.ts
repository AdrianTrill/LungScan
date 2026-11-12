/** The FastAPI backend (backend/app). */
import { API_URL } from "../config";
import type {
  AnalyzeResult,
  Case,
  CaseDetail,
  Patient,
  PatientDetail,
  UploadResult,
} from "../types";
import type { LungScanApi, ModelStatus } from "./types";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, init);
  } catch {
    throw new Error(`Cannot reach the LungScan API at ${API_URL}. Is the backend running?`);
  }
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail || `HTTP ${response.status}: ${response.statusText}`);
  }
  return response.json();
}

function json(method: string, body: unknown): RequestInit {
  return { method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) };
}

function form(file: File, fields: Record<string, string | undefined> = {}): FormData {
  const data = new FormData();
  data.append("scan", file);
  for (const [key, value] of Object.entries(fields)) if (value) data.append(key, value);
  return data;
}

export const serverApi: LungScanApi = {
  mode: "server",
  listCases: () => request<Case[]>("/api/cases"),
  getCase: (id) => request<CaseDetail>(`/api/cases/${encodeURIComponent(id)}`),
  deleteCase: async (id) => {
    await request(`/api/cases/${encodeURIComponent(id)}`, { method: "DELETE" });
  },
  uploadScan: (file, patientId) =>
    request<UploadResult>("/api/upload", {
      method: "POST",
      body: form(file, { patient_id: patientId }),
    }),
  replaceScan: (caseId, file) =>
    request<UploadResult>(`/api/cases/${encodeURIComponent(caseId)}/replace-scan`, {
      method: "PUT",
      body: form(file),
    }),
  analyzeCase: async (caseId, onProgress) => {
    onProgress?.({ phase: "analyze" });
    return request<AnalyzeResult>(`/api/analyze/${encodeURIComponent(caseId)}`, { method: "POST" });
  },
  saveNotes: async (caseId, notes) => {
    await request(`/api/cases/${encodeURIComponent(caseId)}/notes`, json("PUT", { notes }));
  },
  exportReport: async (caseId, notes) => {
    const response = await fetch(
      `${API_URL}/api/report/${encodeURIComponent(caseId)}`,
      json("POST", { notes })
    );
    if (!response.ok) throw new Error("Report generation failed");
    const disposition = response.headers.get("Content-Disposition") ?? "";
    const filename =
      disposition.match(/filename="(.+)"/)?.[1] ?? `lungscan_report_${caseId.slice(0, 8)}.txt`;
    return { filename, text: await response.text() };
  },
  assignCase: (caseId, patientId) =>
    request<Case>(
      `/api/cases/${encodeURIComponent(caseId)}/assign/${encodeURIComponent(patientId)}`,
      {
        method: "POST",
      }
    ),
  listPatients: () => request<Patient[]>("/api/patients"),
  getPatient: (id) => request<PatientDetail>(`/api/patients/${encodeURIComponent(id)}`),
  createPatient: (patient) => request<Patient>("/api/patients", json("POST", patient)),
  deletePatient: async (id) => {
    await request(`/api/patients/${encodeURIComponent(id)}`, { method: "DELETE" });
  },
  imageUrl: async (study) =>
    `${API_URL}/api/cases/${encodeURIComponent(study.id)}/image?v=${encodeURIComponent(study.updated_at)}`,
  modelStatus: () => request<ModelStatus>("/api/model"),
};
