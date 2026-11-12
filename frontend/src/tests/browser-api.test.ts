/**
 * @jest-environment node
 *
 * The browser runtime's backend, on an in-memory IndexedDB, seeded from the real samples.
 */
import "fake-indexeddb/auto";
import { readFileSync } from "node:fs";
import { join } from "node:path";

jest.mock("@/lib/inference/preprocess", () => ({
  ...jest.requireActual("@/lib/inference/preprocess"),
  decodeRgb: jest.fn(async (blob: Blob) => {
    const bytes = new Uint8Array(await blob.arrayBuffer());
    if (bytes[0] !== 0x89) throw new Error("not an image");
    return { rgb: new Uint8Array(3), width: 1, height: 1 };
  }),
}));

import { browserApi as api } from "@/lib/api/browser";

const samples = join(__dirname, "..", "..", "..", "model", "samples");

beforeAll(() => {
  global.fetch = jest.fn(async (url: string | URL | Request) => {
    const path = String(url).replace(/^\/samples\//, "");
    return new Response(readFileSync(join(samples, path)));
  }) as typeof fetch;
});

const png = (name: string) =>
  new File([new Uint8Array([0x89, 0x50, 0x4e, 0x47])], name, { type: "image/png" });

describe("the browser runtime", () => {
  it("starts with the sample studies, newest first", async () => {
    const cases = await api.listCases();
    expect(cases.map((c) => c.id)).toEqual([
      "sample-01",
      "sample-02",
      "sample-03",
      "sample-04",
      "sample-05",
      "sample-06",
      "sample-07",
    ]);
    const detail = await api.getCase("sample-01");
    expect(detail.patient?.last_name).toBe("Smith");
    expect(detail.analysis_result?.flagged).toBe(true);
    expect(detail.notes).toMatch(/^Demo note/);
  });

  it("keeps patients sorted, and protects those with studies", async () => {
    const patient = await api.createPatient({
      first_name: " Ada ",
      last_name: "Lovelace",
      date_of_birth: "1970-01-02",
    });
    expect(patient.first_name).toBe("Ada");
    const names = (await api.listPatients()).map((p) => p.last_name);
    expect(names).toEqual([...names].sort());
    await expect(api.deletePatient("patient-001")).rejects.toThrow("has associated cases");
    await api.deletePatient(patient.id);
    await expect(api.getPatient(patient.id)).rejects.toThrow("not found");
  });

  it("adds an upload as a pending study, and checks the file", async () => {
    const upload = await api.uploadScan(png("My Scan (1).png"), "patient-002");
    expect(upload.filename).toBe("My Scan _1.png");
    const detail = await api.getCase(upload.case_id);
    expect(detail.case.status).toBe("pending");
    expect(detail.patient?.id).toBe("patient-002");
    await expect(
      api.uploadScan(new File(["%PDF"], "x.pdf", { type: "application/pdf" }))
    ).rejects.toThrow("PNG or JPEG");
    await expect(
      api.uploadScan(new File(["nope"], "x.png", { type: "image/png" }))
    ).rejects.toThrow("readable");
    await expect(api.uploadScan(png("x.png"), "patient-missing")).rejects.toThrow("not found");
  });

  it("replacing a scan clears the read and keeps the notes", async () => {
    await api.saveNotes("sample-02", "Compare with prior");
    const replaced = await api.replaceScan("sample-02", png("new.png"));
    expect(replaced.filename).toBe("new.png");
    const detail = await api.getCase("sample-02");
    expect(detail.analysis_result).toBeNull();
    expect(detail.case).toMatchObject({
      status: "pending",
      cancer_probability: null,
      dataset_label: null,
    });
    expect(detail.notes).toBe("Compare with prior");
  });

  it("exports a report with the notes, and deletes studies", async () => {
    const { filename, text } = await api.exportReport("sample-03", "Follow up in 3 months.");
    expect(filename).toBe("lungscan_report_sample-0.txt");
    expect(text).toContain("Michael Williams, MRN-2024-003");
    expect(text).toContain("Follow up in 3 months.");
    await api.deleteCase("sample-03");
    await expect(api.getCase("sample-03")).rejects.toThrow("not found");
  });

  it("starts over from the samples", async () => {
    await api.reset!();
    expect((await api.listCases()).length).toBe(7);
    expect((await api.getCase("sample-02")).analysis_result).not.toBeNull();
  });
});
