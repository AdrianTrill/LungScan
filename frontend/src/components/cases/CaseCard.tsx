/** Case card component for displaying case information in a list. */

import { motion } from "framer-motion";
import { Case } from "@/lib/types";
import Badge from "../ui/Badge";
import Button from "../ui/Button";

interface CaseCardProps {
  case: Case;
  onDelete: (caseId: string) => void;
  onView: (caseId: string) => void;
  onAnalyze?: (caseId: string) => void;
  index?: number;
  noduleCount?: number;
  imageThumbnailUrl?: string;
}

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function CaseCard({ case: caseData, onDelete, onView, onAnalyze, index = 0, noduleCount, imageThumbnailUrl }: CaseCardProps) {
  const handleDelete = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (confirm(`Are you sure you want to delete case "${caseData.filename}"?`)) {
      onDelete(caseData.id);
    }
  };

  const handleAnalyze = async (e: React.MouseEvent) => {
    e.stopPropagation();
    if (onAnalyze) {
      onAnalyze(caseData.id);
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
        {/* Image Thumbnail */}
        {imageThumbnailUrl && (
          <div className="flex-shrink-0 w-24 h-24 rounded-lg overflow-hidden border border-slate-200 bg-slate-100">
            <img
              src={imageThumbnailUrl}
              alt={caseData.filename}
              className="w-full h-full object-cover"
              onError={(e) => {
                // Hide thumbnail if image fails to load
                (e.target as HTMLImageElement).style.display = 'none';
              }}
            />
          </div>
        )}
        <div className="flex-1 min-w-0 flex flex-col">
          {/* Top row: Filename and Case ID (top right) */}
          <div className="flex items-start justify-between gap-4 mb-2">
            <div className="flex items-center gap-2 min-w-0 flex-1">
              <svg className="w-5 h-5 text-primary-600 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              <h3 className="text-lg font-semibold text-slate-900 group-hover:text-primary-700 transition-colors truncate">
                {caseData.filename}
              </h3>
            </div>
            {/* Case ID - Top Right */}
            <div className="flex items-center gap-1.5 px-2 py-1 bg-slate-50 rounded border border-slate-200 flex-shrink-0">
              <svg className="w-3.5 h-3.5 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 20l4-16m2 16l4-16M6 9h14M4 15h14" />
              </svg>
              <span className="text-xs text-slate-500 font-medium">ID:</span>
              <span className="text-xs font-mono text-slate-700 font-semibold truncate max-w-[200px]" title={caseData.id}>
                {caseData.id}
              </span>
            </div>
          </div>
          {/* Second row: Badges */}
          <div className="flex items-center gap-2 mb-3 flex-wrap">
            <Badge status={caseData.status} />
            {caseData.status === "analyzed" && noduleCount !== undefined && (
              <span className={`text-xs px-2.5 py-1 rounded-full font-semibold ${
                noduleCount === 0 
                  ? "bg-green-100 text-green-700" 
                  : noduleCount <= 2 
                  ? "bg-yellow-100 text-yellow-700"
                  : "bg-red-100 text-red-700"
              }`}>
                {noduleCount} {noduleCount === 1 ? "Nodule" : "Nodules"}
              </span>
            )}
            {caseData.patient_id && (
              <span className="text-xs px-2 py-1 bg-slate-100 text-slate-600 rounded-full">
                Patient Assigned
              </span>
            )}
          </div>
          {/* Bottom row: Timestamp and Action Buttons */}
          <div className="flex items-center justify-between gap-4 mt-auto">
            <div className="flex items-center gap-2 text-sm text-slate-500">
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <span>Updated {new Date(caseData.updated_at).toLocaleDateString()} at {new Date(caseData.updated_at).toLocaleTimeString()}</span>
            </div>
            {/* Action Buttons - Bottom Right */}
            <div className="flex items-center gap-2 flex-shrink-0">
              {onAnalyze && (
                <Button
                  variant="primary"
                  onClick={handleAnalyze}
                >
                  <svg className="w-4 h-4 mr-1.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" />
                  </svg>
                  {caseData.status === "pending" ? "Analyze" : "Re-analyze"}
                </Button>
              )}
              <Button
                variant="danger"
                onClick={handleDelete}
              >
                <svg className="w-4 h-4 mr-1.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                </svg>
                Delete
              </Button>
            </div>
          </div>
        </div>
      </div>
    </motion.div>
  );
}

