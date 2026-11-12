"use client";

import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { RUNTIME, asset } from "@/lib/config";
import { megabytes } from "@/lib/format";
import type { Patient } from "@/lib/types";
import Button from "../ui/Button";
import Dialog from "../ui/Dialog";
import Icon from "../ui/Icon";

const SAMPLES = ["sample-01", "sample-02", "sample-03", "sample-05", "sample-04", "sample-06"];

/** Upload a slice for a new study, from a file or one of the sample slices. */
export default function UploadDialog({
  open,
  onClose,
  onUploaded,
  patientId,
}: {
  open: boolean;
  onClose: () => void;
  onUploaded: (caseId: string) => void;
  patientId?: string;
}) {
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [patients, setPatients] = useState<Patient[]>([]);
  const [patient, setPatient] = useState(patientId ?? "");
  const [dragging, setDragging] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const input = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!open) return;
    setFile(null);
    setError(null);
    setPatient(patientId ?? "");
    api
      .listPatients()
      .then(setPatients)
      .catch(() => setPatients([]));
  }, [open, patientId]);

  useEffect(() => {
    if (!file) {
      setPreview(null);
      return;
    }
    const url = URL.createObjectURL(file);
    setPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  const choose = (candidate: File | undefined) => {
    setError(null);
    if (!candidate) return;
    if (!["image/png", "image/jpeg"].includes(candidate.type)) {
      setError("Choose a PNG or JPEG slice");
      return;
    }
    setFile(candidate);
  };

  const pickSample = async (id: string) => {
    const response = await fetch(asset(`samples/images/${id}.png`));
    choose(new File([await response.blob()], `${id}.png`, { type: "image/png" }));
  };

  const submit = async () => {
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      const result = await api.uploadScan(file, patient || undefined);
      onUploaded(result.case_id);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Upload failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="New study"
      description={
        RUNTIME === "browser"
          ? "The slice stays in this browser; the model reads it here."
          : "The slice is uploaded to the LungScan server and read there."
      }
      wide
    >
      <div
        onDragOver={(event) => {
          event.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(event) => {
          event.preventDefault();
          setDragging(false);
          choose(event.dataTransfer.files[0]);
        }}
        onClick={() => input.current?.click()}
        className={`flex cursor-pointer items-center gap-4 rounded-xl border-2 border-dashed p-4 transition ${
          dragging
            ? "border-accent bg-accent/10"
            : "border-line-strong hover:border-accent/60 hover:bg-line/20"
        }`}
        data-testid="dropzone"
      >
        <div className="grid h-24 w-24 flex-none place-items-center overflow-hidden rounded-lg bg-viewer">
          {preview ? (
            // eslint-disable-next-line @next/next/no-img-element -- a local object URL
            <img src={preview} alt="" className="h-full w-full object-cover" />
          ) : (
            <Icon name="upload" className="h-7 w-7 text-slate-500" />
          )}
        </div>
        <div className="min-w-0">
          <p className="text-[13.5px] font-medium text-ink">
            {file ? file.name : "Drop an axial CT slice here, or click to choose one"}
          </p>
          <p className="mt-0.5 text-[12px] text-muted">
            {file
              ? megabytes(file.size)
              : "PNG or JPEG, up to 25 MB. The model expects a single 2D slice."}
          </p>
        </div>
        <input
          ref={input}
          type="file"
          accept="image/png,image/jpeg"
          className="hidden"
          onChange={(event) => choose(event.target.files?.[0])}
          data-testid="file-input"
        />
      </div>

      <div className="mt-4">
        <p className="eyebrow mb-2">No slice at hand? Use a test slice</p>
        <div className="flex gap-2 overflow-x-auto pb-1">
          {SAMPLES.map((id) => (
            <button
              key={id}
              type="button"
              onClick={() => void pickSample(id)}
              className="h-14 w-14 flex-none overflow-hidden rounded-lg border border-line bg-viewer transition hover:border-accent"
              title={`Use ${id}`}
            >
              {/* eslint-disable-next-line @next/next/no-img-element -- static sample */}
              <img
                src={asset(`samples/images/${id}.png`)}
                alt=""
                className="h-full w-full object-cover"
              />
            </button>
          ))}
        </div>
      </div>

      <label className="mt-4 block">
        <span className="eyebrow">Patient</span>
        <select
          value={patient}
          onChange={(event) => setPatient(event.target.value)}
          className="field mt-1.5"
        >
          <option value="">Unassigned</option>
          {patients.map((p) => (
            <option key={p.id} value={p.id}>
              {p.last_name}, {p.first_name}{" "}
              {p.medical_record_number ? `· ${p.medical_record_number}` : ""}
            </option>
          ))}
        </select>
      </label>

      {error && <p className="mt-3 text-[12.5px] text-flag">{error}</p>}

      <div className="mt-5 flex justify-end gap-2">
        <Button variant="ghost" onClick={onClose}>
          Cancel
        </Button>
        <Button
          variant="primary"
          icon="scan"
          disabled={!file || busy}
          onClick={() => void submit()}
        >
          {busy ? (RUNTIME === "browser" ? "Saving…" : "Uploading and reading…") : "Add and read"}
        </Button>
      </div>
    </Dialog>
  );
}
