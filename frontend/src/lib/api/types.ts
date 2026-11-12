import type { RuntimeMode } from "../config";
import type {
  AnalyzeResult,
  Case,
  CaseDetail,
  Patient,
  PatientCreate,
  PatientDetail,
  UploadResult,
} from "../types";

export interface AnalyzeProgress {
  phase: "manifest" | "download" | "verify" | "cache" | "compile" | "analyze";
  loaded?: number;
  total?: number;
}

export interface ModelStatus {
  runtime: string;
  source: string;
  /** Whether the model is on hand: on the server's disk, or in this browser's cache. */
  available: boolean;
  bytes?: number;
}

/** What the app needs from a backend. The FastAPI server and the browser both provide it. */
export interface LungScanApi {
  mode: RuntimeMode;
  listCases(): Promise<Case[]>;
  getCase(id: string): Promise<CaseDetail>;
  deleteCase(id: string): Promise<void>;
  uploadScan(file: File, patientId?: string): Promise<UploadResult>;
  replaceScan(caseId: string, file: File): Promise<UploadResult>;
  analyzeCase(
    caseId: string,
    onProgress?: (progress: AnalyzeProgress) => void
  ): Promise<AnalyzeResult>;
  saveNotes(caseId: string, notes: string): Promise<void>;
  exportReport(caseId: string, notes: string): Promise<{ filename: string; text: string }>;
  assignCase(caseId: string, patientId: string): Promise<Case>;
  listPatients(): Promise<Patient[]>;
  getPatient(id: string): Promise<PatientDetail>;
  createPatient(patient: PatientCreate): Promise<Patient>;
  deletePatient(id: string): Promise<void>;
  /** A URL the browser can display the case's slice from. */
  imageUrl(study: Case): Promise<string>;
  modelStatus(): Promise<ModelStatus>;
  /** Start over with the sample studies (browser only). */
  reset?(): Promise<void>;
}
