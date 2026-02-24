/** Status badge component. */

import { motion } from "framer-motion";

interface BadgeProps {
  status: "pending" | "analyzed";
  className?: string;
}

export default function Badge({ status, className = "" }: BadgeProps) {
  const baseClasses = "inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold shadow-sm";
  const statusClasses = {
    pending: "bg-amber-100 text-amber-800 border border-amber-200",
    analyzed: "bg-emerald-100 text-emerald-800 border border-emerald-200",
  };

  return (
    <motion.span
      initial={{ scale: 0, opacity: 0 }}
      animate={{ scale: 1, opacity: 1 }}
      transition={{ type: "spring", stiffness: 300, damping: 20 }}
      whileHover={{ scale: 1.1 }}
      className={`${baseClasses} ${statusClasses[status]} ${className}`}
    >
      {status === "pending" ? "Pending" : "Analyzed"}
    </motion.span>
  );
}

