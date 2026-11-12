"use client";

import { useEffect, useRef, useState } from "react";
import toast from "react-hot-toast";
import { api } from "@/lib/api";
import { useShortcuts } from "@/lib/hooks";
import Button from "../ui/Button";

export function downloadText(filename: string, text: string) {
  const url = URL.createObjectURL(new Blob([text], { type: "text/plain;charset=utf-8" }));
  const link = Object.assign(document.createElement("a"), { href: url, download: filename });
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

/** The reader's notes, saved as they type, and the report export. */
export default function NotesPanel({ caseId, initial }: { caseId: string; initial: string }) {
  const [notes, setNotes] = useState(initial);
  const [state, setState] = useState<"saved" | "saving" | "unsaved">("saved");
  const timer = useRef<ReturnType<typeof setTimeout>>();
  const latest = useRef(notes);
  latest.current = notes;

  useEffect(() => {
    setNotes(initial);
    setState("saved");
  }, [caseId, initial]);

  const save = async (value: string) => {
    setState("saving");
    try {
      await api.saveNotes(caseId, value);
      if (latest.current === value) setState("saved");
    } catch (error) {
      setState("unsaved");
      toast.error(error instanceof Error ? error.message : "Could not save the notes");
    }
  };

  const onChange = (value: string) => {
    setNotes(value);
    setState("unsaved");
    clearTimeout(timer.current);
    timer.current = setTimeout(() => void save(value), 600);
  };

  useEffect(() => () => clearTimeout(timer.current), []);

  const exportReport = async () => {
    clearTimeout(timer.current);
    try {
      const { filename, text } = await api.exportReport(caseId, latest.current);
      setState("saved");
      downloadText(filename, text);
      toast.success("Report downloaded");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not generate the report");
    }
  };

  useShortcuts({ e: () => void exportReport() });

  return (
    <section className="panel p-4" aria-label="Notes and report">
      <div className="flex items-center justify-between">
        <h2 className="eyebrow">Notes</h2>
        <span className="text-[11.5px] text-muted" aria-live="polite">
          {state === "saved" ? "Saved" : state === "saving" ? "Saving…" : "Unsaved"}
        </span>
      </div>
      <textarea
        value={notes}
        onChange={(event) => onChange(event.target.value)}
        placeholder="Findings, comparison with prior studies, recommendation…"
        rows={6}
        className="field mt-2 resize-y text-[13px] leading-relaxed"
        aria-label="Notes"
      />
      <div className="mt-3 flex items-center justify-between gap-2">
        <p className="text-[11.5px] text-muted">
          The report includes the read, the regions, and these notes.
        </p>
        <Button size="sm" icon="download" shortcut="E" onClick={() => void exportReport()}>
          Export
        </Button>
      </div>
    </section>
  );
}
