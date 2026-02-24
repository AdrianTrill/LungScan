"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import toast from "react-hot-toast";
import { useParams, useRouter } from "next/navigation";
import { api } from "@/lib/api";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
import { CaseDetail, Nodule } from "@/lib/types";
import { calculateAge } from "@/lib/utils";
import FileDropzone from "@/components/upload/FileDropzone";
import ScanViewer from "@/components/viewer/ScanViewer";
import NotesEditor from "@/components/report/NotesEditor";
import AnalysisCharts from "@/components/report/AnalysisCharts";
import Badge from "@/components/ui/Badge";
import Button from "@/components/ui/Button";

export default function CaseDetailPage() {
  const params = useParams();
  const router = useRouter();
  const caseId = params.id as string;
  const [caseDetail, setCaseDetail] = useState<CaseDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);
  const [imageUrl, setImageUrl] = useState<string | null>(null);
  const [selectedNodule, setSelectedNodule] = useState<Nodule | null>(null);
  const [patients, setPatients] = useState<Array<{id: string, first_name: string, last_name: string}>>([]);
  const [showAssignPatient, setShowAssignPatient] = useState(false);
  const [selectedPatientId, setSelectedPatientId] = useState<string>("");
  
  // Get patient_id from URL search params if creating new case
  const searchParams = typeof window !== "undefined" ? new URLSearchParams(window.location.search) : null;
  const patientIdFromUrl = searchParams?.get("patient_id");

  useEffect(() => {
    if (caseId && caseId !== "new") {
      loadCase();
      loadPatients();
    }
  }, [caseId]);

  const loadPatients = async () => {
    try {
      const data = await api.getPatients();
      setPatients(data.map(p => ({ id: p.id, first_name: p.first_name, last_name: p.last_name })));
    } catch (error) {
      console.error("Failed to load patients:", error);
    }
  };

  const loadCase = async () => {
    try {
      setLoading(true);
      const data = await api.getCase(caseId);
      setCaseDetail(data);
      // Always try to load the image URL (for both pending and analyzed cases)
      // Add cache-busting parameter based on case updated_at timestamp
      const timestamp = data.case.updated_at ? new Date(data.case.updated_at).getTime() : Date.now();
      const imageUrlPath = `${API_URL}/api/cases/${caseId}/image?t=${timestamp}`;
      // Set image URL - it will load when the image endpoint is called
      setImageUrl(imageUrlPath);
    } catch (error) {
      console.error("Failed to load case:", error);
      toast.error("Failed to load case");
    } finally {
      setLoading(false);
    }
  };

  const handleFileUpload = async (file: File, patientId?: string) => {
    const toastId = toast.loading("Uploading scan...");
    try {
      const result = await api.uploadScan(file, patientId);
      toast.success("Scan uploaded successfully! Analysis starting...", { id: toastId });
      
      // If uploaded from patient page, redirect back to patient page
      if (patientId) {
        router.push(`/patients/${patientId}`);
      } else {
        // Otherwise, navigate to the new case
        router.push(`/cases/${result.case_id}`);
      }
    } catch (error) {
      console.error("Upload failed:", error);
      toast.error("Upload failed. Please try again.", { id: toastId });
    }
  };

  const handleReplaceScan = async (file: File) => {
    if (!caseDetail) return;
    
    const toastId = toast.loading("Replacing scan...");
    try {
      await api.replaceCaseScan(caseDetail.case.id, file);
      toast.success("Scan replaced successfully! Case status reset to pending.", { id: toastId });
      // Reload case to get updated information
      await loadCase();
    } catch (error) {
      console.error("Replace scan failed:", error);
      toast.error("Failed to replace scan. Please try again.", { id: toastId });
    }
  };

  const handleAssignPatient = async () => {
    if (!caseDetail || !selectedPatientId) return;
    
    const toastId = toast.loading("Assigning patient...");
    try {
      await api.assignCaseToPatient(caseDetail.case.id, selectedPatientId);
      toast.success("Patient assigned successfully!", { id: toastId });
      setShowAssignPatient(false);
      setSelectedPatientId("");
      await loadCase();
    } catch (error: any) {
      console.error("Assign patient failed:", error);
      const errorMessage = error.message || "Failed to assign patient";
      if (errorMessage.includes("already has")) {
        toast.error(errorMessage, { id: toastId, duration: 5000 });
      } else {
        toast.error("Failed to assign patient. Please try again.", { id: toastId });
      }
    }
  };

  const handleAnalyze = async () => {
    if (!caseDetail) return;

    const toastId = toast.loading("Analyzing scan... This may take a few seconds.");
    try {
      setAnalyzing(true);
      await api.analyzeCase(caseDetail.case.id);
      // Reload case to get updated analysis results and status
      await loadCase();
      // Image URL is already set in loadCase() with cache-busting
      toast.success("Analysis completed successfully!", { id: toastId });
    } catch (error) {
      console.error("Analysis failed:", error);
      toast.error("Analysis failed. Please try again.", { id: toastId });
    } finally {
      setAnalyzing(false);
    }
  };

  const handleExportReport = async (notes: string) => {
    if (!caseDetail) return;

    const toastId = toast.loading("Generating report...");
    try {
      await api.generateReport(caseDetail.case.id, notes);
      toast.success("Report downloaded successfully!", { id: toastId });
    } catch (error) {
      console.error("Report generation failed:", error);
      toast.error("Failed to generate report", { id: toastId });
    }
  };

  if (caseId === "new") {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50/30 to-slate-50">
        <div className="container mx-auto px-4 sm:px-6 lg:px-8 py-8 lg:py-12">
          <button
            onClick={() => router.push("/")}
            className="mb-6 inline-flex items-center gap-2 text-primary-600 hover:text-primary-700 font-medium transition-colors"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
            </svg>
            Back to Cases
          </button>
          <div className="bg-white rounded-2xl card-shadow-lg p-8 lg:p-12 max-w-3xl mx-auto">
            <h2 className="text-3xl font-bold mb-2 text-slate-900">Upload New Scan</h2>
            <p className="text-slate-600 mb-6">Upload a CT scan image to begin analysis</p>
            {patientIdFromUrl && (
              <div className="mb-4 p-4 bg-blue-50 rounded-lg border border-blue-200">
                <p className="text-sm text-blue-800">
                  This scan will be assigned to the selected patient
                </p>
              </div>
            )}
            <FileDropzone onFileSelect={(file) => handleFileUpload(file, patientIdFromUrl || undefined)} />
          </div>
        </div>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50/30 to-slate-50 flex items-center justify-center">
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="text-center"
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
            Loading case...
          </motion.p>
        </motion.div>
      </div>
    );
  }

  if (!caseDetail) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50/30 to-slate-50 flex items-center justify-center">
        <div className="text-center bg-white rounded-xl p-8 card-shadow">
          <svg className="w-16 h-16 mx-auto text-red-500 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <p className="text-lg font-semibold text-slate-900 mb-2">Case not found</p>
          <p className="text-slate-600 mb-4">The case you're looking for doesn't exist.</p>
          <button
            onClick={() => router.push("/")}
            className="gradient-primary text-white px-6 py-2 rounded-xl font-semibold hover:shadow-lg transition-all"
          >
            Back to Cases
          </button>
        </div>
      </div>
    );
  }

  const nodules = caseDetail.analysis_result?.nodules || [];
  
  // Calculate step numbers dynamically - always show sequential 1, 2, 3
  const getStepNumber = (section: "upload" | "analyze" | "viewer" | "report"): number => {
    const isAnalyzed = caseDetail.case.status === "analyzed";
    const showUpload = !imageUrl && !isAnalyzed;
    const showAnalyze = (imageUrl && !isAnalyzed) || isAnalyzed; // Show for both pending and analyzed
    const showViewer = isAnalyzed && imageUrl; // Show viewer for all analyzed cases
    const showReport = isAnalyzed;
    
    // Count which step this section is
    let step = 1;
    if (section === "upload" && showUpload) return step;
    if (showUpload) step++;
    if (section === "analyze" && showAnalyze) return step;
    if (showAnalyze) step++;
    if (section === "viewer" && showViewer) return step;
    if (showViewer) step++;
    if (section === "report" && showReport) return step;
    
    return 1;
  };

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.3 }}
      className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50/30 to-slate-50"
    >
      <div className="container mx-auto px-4 sm:px-6 lg:px-8 py-8 lg:py-12">
        <motion.button
          initial={{ opacity: 0, x: -20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.1 }}
          onClick={() => router.push("/")}
          whileHover={{ x: -4 }}
          className="mb-6 inline-flex items-center gap-2 text-primary-600 hover:text-primary-700 font-medium transition-colors"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
          </svg>
          Back to Cases
        </motion.button>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          className="mb-8 bg-white rounded-2xl card-shadow-lg p-6 lg:p-8"
        >
          <div className="flex items-start justify-between gap-4 mb-2">
            <div className="flex-1">
              <h1 className="text-3xl lg:text-4xl font-bold text-slate-900 mb-2">
                {caseDetail.case.filename}
              </h1>
              <div className="flex items-center gap-3 flex-wrap">
                <Badge status={caseDetail.case.status} />
                <div className="flex items-center gap-2 px-3 py-1.5 bg-slate-100 rounded-lg border border-slate-200">
                  <svg className="w-4 h-4 text-slate-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 20l4-16m2 16l4-16M6 9h14M4 15h14" />
                  </svg>
                  <span className="text-sm text-slate-600 font-medium">Case ID:</span>
                  <span 
                    className="font-mono text-sm text-slate-900 font-semibold cursor-pointer hover:text-primary-600 transition-colors"
                    onClick={(e) => {
                      e.stopPropagation();
                      navigator.clipboard.writeText(caseDetail.case.id);
                      toast.success("Case ID copied to clipboard!");
                    }}
                    title="Click to copy"
                  >
                    {caseDetail.case.id}
                  </span>
                </div>
                {caseDetail.patient ? (
                  <div className="flex items-center gap-2 text-sm">
                    <svg className="w-4 h-4 text-primary-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                    </svg>
                    <span className="text-slate-700">
                      {caseDetail.patient.first_name} {caseDetail.patient.last_name}
                      {caseDetail.patient.date_of_birth && (
                        <span className="text-slate-500 ml-2">
                          (Age: {calculateAge(caseDetail.patient.date_of_birth)})
                        </span>
                      )}
                    </span>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        router.push(`/patients/${caseDetail.patient!.id}`);
                      }}
                      className="text-primary-600 hover:text-primary-700 underline"
                    >
                      View Patient
                    </button>
                  </div>
                ) : (
                  <div className="flex items-center gap-2">
                    {!showAssignPatient ? (
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setShowAssignPatient(true);
                        }}
                        className="text-sm px-3 py-1.5 bg-primary-50 text-primary-700 rounded-lg border border-primary-200 hover:bg-primary-100 transition-colors flex items-center gap-2"
                      >
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                        </svg>
                        Assign Patient
                      </button>
                    ) : (
                      <div className="flex items-center gap-2">
                        <select
                          value={selectedPatientId}
                          onChange={(e) => setSelectedPatientId(e.target.value)}
                          onClick={(e) => e.stopPropagation()}
                          className="text-sm px-3 py-1.5 border border-slate-300 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-primary-500"
                        >
                          <option value="">Select a patient...</option>
                          {patients.map((patient) => (
                            <option key={patient.id} value={patient.id}>
                              {patient.first_name} {patient.last_name}
                            </option>
                          ))}
                        </select>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            handleAssignPatient();
                          }}
                          disabled={!selectedPatientId}
                          className="text-sm px-3 py-1.5 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:bg-slate-300 disabled:cursor-not-allowed transition-colors"
                        >
                          Assign
                        </button>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setShowAssignPatient(false);
                            setSelectedPatientId("");
                          }}
                          className="text-sm px-3 py-1.5 bg-slate-200 text-slate-700 rounded-lg hover:bg-slate-300 transition-colors"
                        >
                          Cancel
                        </button>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          </div>
        </motion.div>

        {/* Upload Section */}
        {!imageUrl && caseDetail.case.status === "pending" && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3 }}
            className="bg-white rounded-2xl card-shadow-lg p-6 lg:p-8 mb-6"
          >
            <div className="flex items-center gap-3 mb-6">
              <div className="w-10 h-10 rounded-full bg-primary-100 flex items-center justify-center">
                <span className="text-primary-600 font-bold">{getStepNumber("upload")}</span>
              </div>
              <h2 className="text-2xl font-bold text-slate-900">Upload Scan</h2>
            </div>
            <FileDropzone onFileSelect={handleFileUpload} />
          </motion.div>
        )}

        {/* Analyze Section - Show for pending cases or allow re-analysis */}
        {(caseDetail.case.status === "pending" || caseDetail.case.status === "analyzed") && (
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: 0.4 }}
            className="bg-white rounded-2xl card-shadow-lg p-6 lg:p-8 mb-6"
          >
            <div className="flex items-center gap-3 mb-6">
              <div className="w-10 h-10 rounded-full bg-primary-100 flex items-center justify-center">
                <span className="text-primary-600 font-bold">
                  {caseDetail.case.status === "pending" ? getStepNumber("analyze") : "↻"}
                </span>
              </div>
              <h2 className="text-2xl font-bold text-slate-900">
                {caseDetail.case.status === "pending" ? "Analyze" : "Re-analyze"}
              </h2>
            </div>
            <p className="text-slate-600 mb-4">
              {caseDetail.case.status === "pending"
                ? "Run AI analysis to detect lung nodules and assess malignancy risk."
                : "Re-run analysis to get updated results with the latest AI model."}
            </p>
            <Button
              onClick={handleAnalyze}
              disabled={analyzing}
              variant="primary"
              className="text-lg px-8 py-3"
            >
              {analyzing ? (
                <>
                  <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                  Analyzing...
                </>
              ) : (
                <>
                  <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" />
                  </svg>
                  {caseDetail.case.status === "pending" ? "Analyze Scan" : "Re-analyze Scan"}
                </>
              )}
            </Button>
          </motion.div>
        )}

        {/* Replace Scan Section - Show option to replace existing scan */}
        {caseDetail.case.status === "analyzed" && imageUrl && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.45 }}
            className="bg-white rounded-2xl card-shadow-lg p-6 lg:p-8 mb-6"
          >
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center">
                  <svg className="w-4 h-4 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
                  </svg>
                </div>
                <h3 className="text-lg font-semibold text-slate-900">Replace Scan</h3>
              </div>
            </div>
            <p className="text-sm text-slate-600 mb-4">
              Upload a new CT scan to replace the current one. This will reset the case status and clear existing analysis results.
            </p>
            <FileDropzone onFileSelect={handleReplaceScan} />
          </motion.div>
        )}

        {/* Viewer Section - Show for analyzed cases with image */}
        {caseDetail.case.status === "analyzed" && imageUrl && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.5 }}
            className="bg-white rounded-2xl card-shadow-lg p-6 lg:p-8 mb-6"
          >
            <div className="flex items-center gap-3 mb-6">
              <div className="w-10 h-10 rounded-full bg-primary-100 flex items-center justify-center">
                <span className="text-primary-600 font-bold">{getStepNumber("viewer")}</span>
              </div>
              <h2 className="text-2xl font-bold text-slate-900">Scan Viewer</h2>
            </div>
            {imageUrl && (
              <ScanViewer
                imageUrl={imageUrl}
                nodules={nodules}
                onNoduleClick={setSelectedNodule}
              />
            )}
            
            {selectedNodule && (
              <motion.div
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ type: "spring", stiffness: 300 }}
                className="mt-6 p-5 bg-gradient-to-br from-blue-50 to-primary-50 rounded-xl border border-blue-200"
              >
                <h3 className="font-bold text-lg mb-3 text-slate-900 flex items-center gap-2">
                  <svg className="w-5 h-5 text-primary-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  Nodule Details
                </h3>
                <div className="space-y-2">
                  <p className="text-sm text-slate-700">
                    <strong className="text-slate-900">Malignancy Score:</strong>{" "}
                    <span className="font-mono font-semibold text-primary-700">
                      {(selectedNodule.malignancy_score * 100).toFixed(1)}%
                    </span>
                  </p>
                  <p className="text-sm text-slate-700">
                    <strong className="text-slate-900">Explanation:</strong> {selectedNodule.explanation}
                  </p>
                </div>
              </motion.div>
            )}
            {caseDetail.analysis_result && (
              <div className="mt-6 p-5 bg-slate-50 rounded-xl border border-slate-200">
                <p className="text-sm text-slate-700 leading-relaxed">
                  {caseDetail.analysis_result.summary}
                </p>
              </div>
            )}
            {nodules.length === 0 && (
              <div className="mt-6 p-5 bg-green-50 rounded-xl border border-green-200">
                <p className="text-sm text-green-800 leading-relaxed">
                  ✓ No suspicious nodules detected. The scan appears normal.
                </p>
              </div>
            )}
          </motion.div>
        )}

        {/* Report Section */}
        {caseDetail.case.status === "analyzed" && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.6 }}
            className="bg-white rounded-2xl card-shadow-lg p-6 lg:p-8"
          >
            <div className="flex items-center gap-3 mb-6">
              <div className="w-10 h-10 rounded-full bg-primary-100 flex items-center justify-center">
                <span className="text-primary-600 font-bold">{getStepNumber("report")}</span>
              </div>
              <h2 className="text-2xl font-bold text-slate-900">Report</h2>
            </div>
            
            {/* Interactive Charts */}
            {nodules.length > 0 && (
              <div className="mb-6">
                <AnalysisCharts nodules={nodules} />
              </div>
            )}
            
            <NotesEditor
              initialNotes={caseDetail.notes || ""}
              onExport={handleExportReport}
            />
          </motion.div>
        )}
      </div>
    </motion.div>
  );
}

