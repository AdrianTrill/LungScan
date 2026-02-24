"use client";

import { useEffect, useState, useMemo } from "react";
import { motion } from "framer-motion";
import toast from "react-hot-toast";
import { api } from "@/lib/api";
import { Case } from "@/lib/types";
import CaseList from "@/components/cases/CaseList";
import { useRouter } from "next/navigation";

type SortOption = "newest" | "oldest" | "filename" | "status";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function HomePage() {
  const router = useRouter();
  const [cases, setCases] = useState<Case[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<"all" | "pending" | "analyzed">("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [sortBy, setSortBy] = useState<SortOption>("newest");
  const [noduleCounts, setNoduleCounts] = useState<Record<string, number>>({});

  useEffect(() => {
    loadCases();
  }, []);

  const loadCases = async () => {
    try {
      setLoading(true);
      const data = await api.getCases();
      setCases(data);
      
      // Fetch nodule counts for analyzed cases
      const counts: Record<string, number> = {};
      const analyzedCases = data.filter(c => c.status === "analyzed");
      
      // Fetch in parallel (limit to avoid too many requests)
      const detailPromises = analyzedCases.slice(0, 20).map(async (caseItem) => {
        try {
          const detail = await api.getCase(caseItem.id);
          if (detail.analysis_result) {
            counts[caseItem.id] = detail.analysis_result.nodules.length;
          }
        } catch (error) {
          // Silently fail for individual cases
        }
      });
      
      await Promise.all(detailPromises);
      setNoduleCounts(counts);
    } catch (error) {
      console.error("Failed to load cases:", error);
      toast.error("Failed to load cases");
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (caseId: string) => {
    try {
      await api.deleteCase(caseId);
      await loadCases();
      toast.success("Case deleted successfully");
    } catch (error) {
      console.error("Failed to delete case:", error);
      toast.error("Failed to delete case");
    }
  };

  const handleAnalyze = async (caseId: string) => {
    const toastId = toast.loading("Analyzing scan...");
    try {
      await api.analyzeCase(caseId);
      await loadCases(); // Refresh to update status
      toast.success("Analysis completed successfully!", { id: toastId });
    } catch (error) {
      console.error("Failed to analyze case", error);
      toast.error("Failed to analyze case. Please try again.", { id: toastId });
    }
  };

  const handleNewCase = () => {
    router.push("/cases/new");
  };

  // Calculate statistics
  const stats = useMemo(() => {
    const total = cases.length;
    const analyzed = cases.filter((c) => c.status === "analyzed").length;
    const pending = cases.filter((c) => c.status === "pending").length;
    return { total, analyzed, pending };
  }, [cases]);

  // Filter and search cases
  const filteredCases = useMemo(() => {
    let result = cases;

    // Apply status filter
    if (filter !== "all") {
      result = result.filter((c) => c.status === filter);
    }

    // Apply search query
    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase();
      result = result.filter(
        (c) =>
          c.filename.toLowerCase().includes(query) ||
          c.id.toLowerCase().includes(query)
      );
    }

    // Apply sorting
    const sorted = [...result].sort((a, b) => {
      switch (sortBy) {
        case "newest":
          return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
        case "oldest":
          return new Date(a.created_at).getTime() - new Date(b.created_at).getTime();
        case "filename":
          return a.filename.localeCompare(b.filename);
        case "status":
          return a.status.localeCompare(b.status);
        default:
          return 0;
      }
    });

    return sorted;
  }, [cases, filter, searchQuery, sortBy]);

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50/30 to-slate-50">
      <div className="container mx-auto px-4 sm:px-6 lg:px-8 py-8 lg:py-12">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="mb-8 lg:mb-12"
        >
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-6">
            <motion.div
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.1 }}
            >
              <h1 className="text-4xl lg:text-5xl font-bold text-slate-900 mb-2">
                LungScan Assist
              </h1>
              <p className="text-lg text-slate-600 max-w-2xl">
                Streamlining CT scan analysis for radiologists
              </p>
            </motion.div>
          <motion.div
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.2 }}
            className="flex gap-3"
          >
            <motion.button
              onClick={() => router.push("/patients")}
              whileHover={{ scale: 1.05, y: -2 }}
              whileTap={{ scale: 0.95 }}
              className="bg-white text-primary-600 px-6 py-3 rounded-xl font-semibold hover:shadow-lg transition-all duration-200 border-2 border-primary-200 hover:border-primary-300 flex items-center gap-2"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
              </svg>
              Patients
            </motion.button>
            <motion.button
              onClick={handleNewCase}
              whileHover={{ scale: 1.05, y: -2 }}
              whileTap={{ scale: 0.95 }}
              className="gradient-primary text-white px-6 py-3 rounded-xl font-semibold hover:shadow-lg transition-all duration-200 flex items-center gap-2"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
              </svg>
              New Case
            </motion.button>
          </motion.div>
          </div>

          {/* Statistics Cards */}
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.25 }}
            className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6"
          >
            <div className="bg-white/80 backdrop-blur-sm rounded-xl p-4 card-shadow border border-slate-200">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-slate-600 mb-1">Total Cases</p>
                  <p className="text-2xl font-bold text-slate-900">{stats.total}</p>
                </div>
                <div className="w-12 h-12 rounded-full bg-primary-100 flex items-center justify-center">
                  <svg className="w-6 h-6 text-primary-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                  </svg>
                </div>
              </div>
            </div>
            <div className="bg-white/80 backdrop-blur-sm rounded-xl p-4 card-shadow border border-slate-200">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-slate-600 mb-1">Analyzed</p>
                  <p className="text-2xl font-bold text-green-600">{stats.analyzed}</p>
                </div>
                <div className="w-12 h-12 rounded-full bg-green-100 flex items-center justify-center">
                  <svg className="w-6 h-6 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                </div>
              </div>
            </div>
            <div className="bg-white/80 backdrop-blur-sm rounded-xl p-4 card-shadow border border-slate-200">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-slate-600 mb-1">Pending</p>
                  <p className="text-2xl font-bold text-yellow-600">{stats.pending}</p>
                </div>
                <div className="w-12 h-12 rounded-full bg-yellow-100 flex items-center justify-center">
                  <svg className="w-6 h-6 text-yellow-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                </div>
              </div>
            </div>
          </motion.div>

          {/* Search and Sort Controls */}
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3 }}
            className="flex flex-col sm:flex-row gap-4 mb-4"
          >
            {/* Search Input */}
            <div className="flex-1 relative">
              <svg className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
              <input
                type="text"
                placeholder="Search by filename or case ID..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-10 pr-4 py-2.5 bg-white/80 backdrop-blur-sm border border-slate-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent text-slate-700 placeholder:text-slate-400"
              />
            </div>

            {/* Sort Dropdown */}
            <div className="relative">
              <select
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value as SortOption)}
                className="appearance-none bg-white/80 backdrop-blur-sm border border-slate-300 rounded-xl px-4 py-2.5 pr-10 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent text-slate-700 cursor-pointer"
              >
                <option value="newest">Newest First</option>
                <option value="oldest">Oldest First</option>
                <option value="filename">Filename (A-Z)</option>
                <option value="status">Status</option>
              </select>
              <svg className="absolute right-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-slate-400 pointer-events-none" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            </div>
          </motion.div>

          {/* Filter Tabs */}
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.35 }}
            className="flex gap-2 bg-white/80 backdrop-blur-sm rounded-xl p-1.5 card-shadow inline-flex"
          >
            <motion.button
              onClick={() => setFilter("all")}
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
              className={`px-5 py-2.5 rounded-lg font-medium transition-all duration-200 ${
                filter === "all"
                  ? "bg-primary-600 text-white shadow-md"
                  : "text-slate-600 hover:text-slate-900 hover:bg-slate-100"
              }`}
            >
              All Cases
            </motion.button>
            <motion.button
              onClick={() => setFilter("pending")}
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
              className={`px-5 py-2.5 rounded-lg font-medium transition-all duration-200 ${
                filter === "pending"
                  ? "bg-primary-600 text-white shadow-md"
                  : "text-slate-600 hover:text-slate-900 hover:bg-slate-100"
              }`}
            >
              Pending
            </motion.button>
            <motion.button
              onClick={() => setFilter("analyzed")}
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
              className={`px-5 py-2.5 rounded-lg font-medium transition-all duration-200 ${
                filter === "analyzed"
                  ? "bg-primary-600 text-white shadow-md"
                  : "text-slate-600 hover:text-slate-900 hover:bg-slate-100"
              }`}
            >
              Analyzed
            </motion.button>
          </motion.div>
        </motion.div>

        {/* Content */}
        {loading ? (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="text-center py-16"
          >
            <motion.div
              animate={{ rotate: 360 }}
              transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
              className="inline-block rounded-full h-12 w-12 border-b-2 border-primary-600 mb-4"
            />
            <motion.p
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.2 }}
              className="text-slate-500 text-lg"
            >
              Loading cases...
            </motion.p>
          </motion.div>
        ) : (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.3 }}
          >
            {filteredCases.length === 0 ? (
              <motion.div
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                className="text-center py-16 bg-white/60 backdrop-blur-sm rounded-2xl border border-slate-200"
              >
                <svg className="w-16 h-16 mx-auto text-slate-400 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                </svg>
                <p className="text-lg font-medium text-slate-600 mb-2">No cases found</p>
                <p className="text-sm text-slate-500">
                  {searchQuery ? "Try adjusting your search or filters" : "Upload a new scan to get started"}
                </p>
              </motion.div>
            ) : (
              <CaseList
                cases={filteredCases}
                onDelete={handleDelete}
                onRefresh={loadCases}
                onAnalyze={handleAnalyze}
                noduleCounts={noduleCounts}
              />
            )}
          </motion.div>
        )}
      </div>
    </div>
  );
}

