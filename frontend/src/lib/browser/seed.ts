/**
 * The browser runtime starts with the same sample studies as the server
 * (backend/app/services/storage.py): model/samples/samples.json, copied into public/samples.
 * Their reads were computed with the same model by backend/tools/make_samples.py.
 */
import { asset } from "../config";
import type { AnalyzeResult, Case, Label, Patient } from "../types";
import * as db from "./db";

interface SampleManifest {
  patients: Omit<Patient, "created_at">[];
  cases: {
    id: string;
    image: string;
    filename: string;
    label: Label;
    patient_id: string;
    notes: string;
    result: Omit<AnalyzeResult, "case_id">;
  }[];
}

const DAY = 24 * 60 * 60 * 1000;
const HOUR = 60 * 60 * 1000;

let seeding: Promise<void> | null = null;

/** Add the samples the first time the app opens in this browser. */
export function ensureSeeded(): Promise<void> {
  if (!seeding) {
    seeding = (async () => {
      if (!(await db.get("meta", "seeded"))) await seed();
    })().catch((error) => {
      seeding = null;
      throw error;
    });
  }
  return seeding;
}

export async function seed(now = Date.now()): Promise<void> {
  const response = await fetch(asset("samples/samples.json"));
  if (!response.ok) throw new Error("The sample studies are missing from this build");
  const manifest: SampleManifest = await response.json();
  for (const [i, patient] of manifest.patients.entries()) {
    await db.put("patients", {
      ...patient,
      created_at: new Date(now - (30 - i) * DAY).toISOString(),
    });
  }
  const count = manifest.cases.length;
  for (const [i, sample] of manifest.cases.entries()) {
    const when = new Date(now - 6 * HOUR * (count - i)).toISOString();
    const image = await fetch(asset(`samples/${sample.image}`));
    await db.put("images", { blob: await image.blob(), name: sample.filename }, sample.id);
    await db.put("results", { ...sample.result, case_id: sample.id, analyzed_at: when });
    const study: Case = {
      id: sample.id,
      filename: sample.filename,
      patient_id: sample.patient_id,
      status: "analyzed",
      created_at: when,
      updated_at: when,
      cancer_probability: sample.result.cancer_probability,
      flagged: sample.result.flagged,
      dataset_label: sample.label,
    };
    await db.put("cases", study);
    if (sample.notes) await db.put("notes", sample.notes, sample.id);
  }
  await db.put("meta", true, "seeded");
}

/** Delete everything and start again with the samples. */
export async function resetDemo(): Promise<void> {
  await seeding?.catch(() => undefined);
  await db.clearAll();
  seeding = null;
  await ensureSeeded();
}
