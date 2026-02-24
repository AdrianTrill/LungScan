"use client";

/** Notes editor component for writing and exporting reports. */

import { useState } from "react";
import Button from "../ui/Button";

interface NotesEditorProps {
  initialNotes: string;
  onExport: (notes: string) => void;
}

export default function NotesEditor({ initialNotes, onExport }: NotesEditorProps) {
  const [notes, setNotes] = useState(initialNotes);

  const handleExport = () => {
    onExport(notes);
  };

  return (
    <div>
      <label className="block text-sm font-semibold text-slate-900 mb-3">
        Clinical Notes
      </label>
      <textarea
        value={notes}
        onChange={(e) => setNotes(e.target.value)}
        placeholder="Enter your clinical notes and observations here..."
        className="w-full h-64 px-4 py-3 border border-slate-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 resize-none text-slate-700 placeholder:text-slate-400 transition-all"
      />
      <div className="mt-6">
        <Button onClick={handleExport} variant="primary" className="text-lg px-8 py-3">
          <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
          </svg>
          Export Report
        </Button>
      </div>
    </div>
  );
}

