/** Case list component. */

import { motion } from "framer-motion";
import { useRouter } from "next/navigation";
import { Case } from "@/lib/types";
import CaseCard from "./CaseCard";

interface CaseListProps {
  cases: Case[];
  onDelete: (caseId: string) => void;
  onRefresh: () => void;
  onAnalyze?: (caseId: string) => void;
}

export default function CaseList({ cases, onDelete, onRefresh, onAnalyze }: CaseListProps) {
  const router = useRouter();

  const handleView = (caseId: string) => {
    router.push(`/cases/${caseId}`);
  };

  if (cases.length === 0) {
    return (
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.3 }}
        className="text-center py-16 bg-white/60 backdrop-blur-sm rounded-2xl border border-slate-200"
      >
        <motion.svg
          initial={{ scale: 0 }}
          animate={{ scale: 1 }}
          transition={{ delay: 0.2, type: "spring", stiffness: 200 }}
          className="w-16 h-16 mx-auto text-slate-400 mb-4"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
        </motion.svg>
        <p className="text-lg font-medium text-slate-600 mb-2">No cases found</p>
        <p className="text-sm text-slate-500">Upload a new scan to get started</p>
      </motion.div>
    );
  }

  return (
    <div className="grid gap-4 sm:gap-5">
      {cases.map((caseData, index) => (
        <CaseCard
          key={caseData.id}
          case={caseData}
          onDelete={onDelete}
          onView={handleView}
          onAnalyze={onAnalyze}
          index={index}
        />
      ))}
    </div>
  );
}

