/**
 * The whole backend, in the browser: studies, patients, and notes in IndexedDB, and the
 * model in ONNX Runtime Web. Scans never leave the page. Behaves like the FastAPI server
 * (backend/app/api/routes), down to its error messages.
 */
import { ensureSeeded, resetDemo } from "../browser/seed";
import * as db from "../browser/db";
import { engine, fetchManifest } from "../inference/engine";
import { interpret } from "../inference/interpret";
import { decodeRgb, toInput } from "../inference/preprocess";
import { generateTextReport, reportFilename } from "../report";
import type { AnalyzeResult, Case, CaseDetail, Patient, PatientDetail } from "../types";
import type { LungScanApi } from "./types";

const TYPES: Record<string, string> = {
  "image/png": ".png",
  "image/jpeg": ".jpg",
  "image/jpg": ".jpg",
};
const MAX_BYTES = 25 * 1024 * 1024;

interface StoredImage {
  blob: Blob;
  name: string;
}

const now = () => new Date().toISOString();
const byUpdated = (a: Case, b: Case) => b.updated_at.localeCompare(a.updated_at);

/** A safe display name, as backend/app/core/utils.py makes it. */
export function displayFilename(name: string, extension: string): string {
  // pathlib's stem: a leading or trailing dot is not an extension.
  const dot = name.lastIndexOf(".");
  const stem = dot > 0 && dot < name.length - 1 ? name.slice(0, dot) : name;
  const cleaned = stem
    .replace(/[^A-Za-z0-9._ -]+/g, "_")
    .replace(/^[ ._]+|[ ._]+$/g, "")
    .slice(0, 96);
  return `${cleaned || "scan"}${extension}`;
}

async function checkScan(file: File): Promise<string> {
  const extension = TYPES[file.type.toLowerCase()];
  if (!extension) throw new Error("Unsupported file type: upload a PNG or JPEG slice");
  if (file.size > MAX_BYTES) throw new Error("The file is larger than 25 MB");
  try {
    await decodeRgb(file);
  } catch {
    throw new Error("The file is not a readable image");
  }
  return extension;
}

async function findCase(id: string): Promise<Case> {
  await ensureSeeded();
  const study = await db.get<Case>("cases", id);
  if (!study) throw new Error(`Case ${id} not found`);
  return study;
}

async function findPatient(id: string): Promise<Patient> {
  const patient = await db.get<Patient>("patients", id);
  if (!patient) throw new Error(`Patient ${id} not found`);
  return patient;
}

async function detail(study: Case): Promise<CaseDetail> {
  return {
    case: study,
    patient: study.patient_id
      ? ((await db.get<Patient>("patients", study.patient_id)) ?? null)
      : null,
    analysis_result: (await db.get<AnalyzeResult>("results", study.id)) ?? null,
    notes: (await db.get<string>("notes", study.id)) ?? null,
  };
}

// One object URL per study, released when its scan is replaced or the study is deleted.
const imageUrls = new Map<string, string>();

function forgetImage(id: string) {
  const url = imageUrls.get(id);
  if (url) URL.revokeObjectURL(url);
  imageUrls.delete(id);
}

export const browserApi: LungScanApi = {
  mode: "browser",

  async listCases() {
    await ensureSeeded();
    return (await db.getAll<Case>("cases")).sort(byUpdated);
  },

  async getCase(id) {
    return detail(await findCase(id));
  },

  async deleteCase(id) {
    await findCase(id);
    await Promise.all([
      db.remove("cases", id),
      db.remove("results", id),
      db.remove("notes", id),
      db.remove("images", id),
    ]);
    forgetImage(id);
  },

  async uploadScan(file, patientId) {
    await ensureSeeded();
    if (patientId) await findPatient(patientId);
    const extension = await checkScan(file);
    const id = crypto.randomUUID();
    const filename = displayFilename(file.name, extension);
    await db.put("images", { blob: file, name: filename } satisfies StoredImage, id);
    const created = now();
    await db.put("cases", {
      id,
      filename,
      patient_id: patientId ?? null,
      status: "pending",
      created_at: created,
      updated_at: created,
      cancer_probability: null,
      flagged: null,
      dataset_label: null,
    } satisfies Case);
    return { case_id: id, filename, patient_id: patientId ?? null, uploaded_at: created };
  },

  async replaceScan(caseId, file) {
    const study = await findCase(caseId);
    const extension = await checkScan(file);
    const filename = displayFilename(file.name, extension);
    await db.put("images", { blob: file, name: filename } satisfies StoredImage, caseId);
    await db.remove("results", caseId);
    const updated: Case = {
      ...study,
      filename,
      status: "pending",
      cancer_probability: null,
      flagged: null,
      dataset_label: null,
      updated_at: now(),
    };
    await db.put("cases", updated);
    forgetImage(caseId);
    return {
      case_id: caseId,
      filename,
      patient_id: study.patient_id,
      uploaded_at: updated.updated_at,
    };
  },

  async analyzeCase(caseId, onProgress) {
    const study = await findCase(caseId);
    const stored = await db.get<StoredImage>("images", caseId);
    if (!stored) throw new Error(`Case ${caseId} has no image to analyze`);
    const image = await decodeRgb(stored.blob);
    const input = toInput(image);
    const stop = onProgress ? engine.onProgress(onProgress) : () => undefined;
    try {
      await engine.load();
      onProgress?.({ phase: "analyze" });
      const output = await engine.run(input);
      const result = interpret(
        {
          logits: output.logits,
          cam: output.cam,
          width: image.width,
          height: image.height,
          inferenceMs: output.ms,
        },
        caseId,
        engine.info!.source,
        engine.runtimeName()
      );
      await db.put("results", result);
      await db.put("cases", {
        ...study,
        status: "analyzed",
        cancer_probability: result.cancer_probability,
        flagged: result.flagged,
        updated_at: now(),
      } satisfies Case);
      return result;
    } finally {
      stop();
    }
  },

  async saveNotes(caseId, notes) {
    await findCase(caseId);
    await db.put("notes", notes, caseId);
  },

  async exportReport(caseId, notes) {
    const study = await findCase(caseId);
    await db.put("notes", notes, caseId);
    return {
      filename: reportFilename(caseId),
      text: generateTextReport(await detail(study), notes),
    };
  },

  async assignCase(caseId, patientId) {
    await findPatient(patientId);
    const study = await findCase(caseId);
    const updated = { ...study, patient_id: patientId, updated_at: now() };
    await db.put("cases", updated);
    return updated;
  },

  async listPatients() {
    await ensureSeeded();
    const patients = await db.getAll<Patient>("patients");
    return patients.sort(
      (a, b) => a.last_name.localeCompare(b.last_name) || a.first_name.localeCompare(b.first_name)
    );
  },

  async getPatient(id): Promise<PatientDetail> {
    await ensureSeeded();
    const patient = await findPatient(id);
    const cases = (await db.getAll<Case>("cases"))
      .filter((c) => c.patient_id === id)
      .sort(byUpdated);
    return { patient, cases };
  },

  async createPatient(input) {
    await ensureSeeded();
    const patient: Patient = {
      id: `patient-${crypto.randomUUID().replace(/-/g, "").slice(0, 8)}`,
      first_name: input.first_name.trim(),
      last_name: input.last_name.trim(),
      date_of_birth: input.date_of_birth,
      medical_record_number: (input.medical_record_number ?? "").trim(),
      created_at: now(),
    };
    if (!patient.first_name || !patient.last_name)
      throw new Error("A patient needs a first and last name");
    await db.put("patients", patient);
    return patient;
  },

  async deletePatient(id) {
    await ensureSeeded();
    await findPatient(id);
    const cases = await db.getAll<Case>("cases");
    if (cases.some((c) => c.patient_id === id)) {
      throw new Error(`Cannot delete patient ${id}: patient has associated cases`);
    }
    await db.remove("patients", id);
  },

  async imageUrl(study) {
    const cached = imageUrls.get(study.id);
    if (cached) return cached;
    const stored = await db.get<StoredImage>("images", study.id);
    if (!stored) throw new Error(`No image for case ${study.id}`);
    const url = URL.createObjectURL(stored.blob);
    imageUrls.set(study.id, url);
    return url;
  },

  async modelStatus() {
    const manifest = await fetchManifest();
    return {
      runtime: engine.runtimeName(),
      source: `${manifest.source.repo}@${manifest.source.revision.slice(0, 7)}`,
      available: await engine.isCached(),
      bytes: manifest.bytes,
    };
  },

  async reset() {
    for (const url of imageUrls.values()) URL.revokeObjectURL(url);
    imageUrls.clear();
    await resetDemo();
  },
};
