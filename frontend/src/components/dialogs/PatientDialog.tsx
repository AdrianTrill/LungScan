"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Patient } from "@/lib/types";
import Button from "../ui/Button";
import Dialog from "../ui/Dialog";

const EMPTY = { first_name: "", last_name: "", date_of_birth: "", medical_record_number: "" };

export default function PatientDialog({
  open,
  onClose,
  onCreated,
}: {
  open: boolean;
  onClose: () => void;
  onCreated: (patient: Patient) => void;
}) {
  const [form, setForm] = useState(EMPTY);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const today = new Date().toISOString().slice(0, 10);

  useEffect(() => {
    if (open) {
      setForm(EMPTY);
      setError(null);
    }
  }, [open]);

  const set = (key: keyof typeof EMPTY) => (event: React.ChangeEvent<HTMLInputElement>) =>
    setForm((f) => ({ ...f, [key]: event.target.value }));

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!form.first_name.trim() || !form.last_name.trim())
      return setError("A first and last name are required");
    if (!form.date_of_birth) return setError("The date of birth is required");
    if (form.date_of_birth > today) return setError("The date of birth cannot be in the future");
    setBusy(true);
    try {
      onCreated(await api.createPatient(form));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not create the patient");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={open} onClose={onClose} title="New patient">
      <form onSubmit={submit} className="space-y-3">
        <div className="grid grid-cols-2 gap-3">
          <label>
            <span className="eyebrow">First name</span>
            <input
              className="field mt-1.5"
              value={form.first_name}
              onChange={set("first_name")}
              autoComplete="off"
            />
          </label>
          <label>
            <span className="eyebrow">Last name</span>
            <input
              className="field mt-1.5"
              value={form.last_name}
              onChange={set("last_name")}
              autoComplete="off"
            />
          </label>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <label>
            <span className="eyebrow">Date of birth</span>
            <input
              type="date"
              max={today}
              className="field mt-1.5"
              value={form.date_of_birth}
              onChange={set("date_of_birth")}
            />
          </label>
          <label>
            <span className="eyebrow">Record number</span>
            <input
              className="field mt-1.5 font-mono"
              value={form.medical_record_number}
              onChange={set("medical_record_number")}
              placeholder="Optional"
              autoComplete="off"
            />
          </label>
        </div>
        {error && <p className="text-[12.5px] text-flag">{error}</p>}
        <div className="flex justify-end gap-2 pt-2">
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" variant="primary" disabled={busy}>
            Create patient
          </Button>
        </div>
      </form>
    </Dialog>
  );
}
