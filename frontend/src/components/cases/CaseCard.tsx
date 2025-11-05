/** Case card component for displaying case information in a list. */

import { motion } from "framer-motion";
import { Case } from "@/lib/types";
import Badge from "../ui/Badge";
import Button from "../ui/Button";

interface CaseCardProps {
  case: Case;
  onDelete: (caseId: string) => void;
  onView: (caseId: string) => void;
  index?: number;
}

export default function CaseCard({ case: caseData, onDelete, onView, index = 0 }: CaseCardProps) {
  const handleDelete = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (confirm(`Are you sure you want to delete case "${caseData.filename}"?`)) {
      onDelete(caseData.id);
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.2 }}
      whileHover={{ y: -2 }}
      className="bg-white rounded-xl card-shadow-lg p-6 hover:shadow-xl transition-all duration-200 cursor-pointer border border-slate-100 hover:border-primary-200 group"
      onClick={() => onView(caseData.id)}
    >
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-3 mb-3 flex-wrap">
            <div className="flex items-center gap-2">
              <svg className="w-5 h-5 text-primary-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              <h3 className="text-lg font-semibold text-slate-900 group-hover:text-primary-700 transition-colors truncate">
                {caseData.filename}
              </h3>
            </div>
            <Badge status={caseData.status} />
            {caseData.patient_id && (
              <span className="text-xs px-2 py-1 bg-slate-100 text-slate-600 rounded-full">
                Patient Assigned
              </span>
            )}
          </div>
          <div className="flex items-center gap-2 text-sm text-slate-500">
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <span>Updated {new Date(caseData.updated_at).toLocaleDateString()} at {new Date(caseData.updated_at).toLocaleTimeString()}</span>
          </div>
        </div>
        <Button
          variant="danger"
          onClick={handleDelete}
          className="ml-4 flex-shrink-0"
        >
          <svg className="w-4 h-4 mr-1.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
          </svg>
          Delete
        </Button>
      </div>
    </motion.div>
  );
}

