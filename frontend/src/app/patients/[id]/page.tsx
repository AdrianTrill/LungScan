"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { PatientDetail } from "@/lib/types";
import Badge from "@/components/ui/Badge";
import CaseCard from "@/components/cases/CaseCard";

export default function PatientDetailPage() {
  const params = useParams();
  const router = useRouter();
  const patientId = params.id as string;
  const [patientDetail, setPatientDetail] = useState<PatientDetail | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (patientId && patientId !== "new") {
      loadPatient();
    }
  }, [patientId]);

  const loadPatient = async () => {
    try {
      setLoading(true);
      const data = await api.getPatient(patientId);
      setPatientDetail(data);
    } catch (error) {
      console.error("Failed to load patient:", error);
      alert("Failed to load patient");
    } finally {
      setLoading(false);
    }
  };

  const calculateAge = (dateOfBirth: string): number => {
    const today = new Date();
    const birth = new Date(dateOfBirth);
    let age = today.getFullYear() - birth.getFullYear();
    const monthDiff = today.getMonth() - birth.getMonth();
    if (monthDiff < 0 || (monthDiff === 0 && today.getDate() < birth.getDate())) {
      age--;
    }
    return age;
  };

  if (patientId === "new") {
    router.push("/patients/new");
    return null;
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50/30 to-slate-50 flex items-center justify-center">
        <div className="text-center">
          <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600 mb-4"></div>
          <p className="text-slate-500 text-lg">Loading patient...</p>
        </div>
      </div>
    );
  }

  if (!patientDetail) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50/30 to-slate-50 flex items-center justify-center">
        <div className="text-center bg-white rounded-xl p-8 card-shadow">
          <p className="text-lg font-semibold text-slate-900 mb-2">Patient not found</p>
          <button
            onClick={() => router.push("/patients")}
            className="gradient-primary text-white px-6 py-2 rounded-xl font-semibold hover:shadow-lg transition-all mt-4"
          >
            Back to Patients
          </button>
        </div>
      </div>
    );
  }

  const { patient, cases } = patientDetail;

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50/30 to-slate-50">
      <div className="container mx-auto px-4 sm:px-6 lg:px-8 py-8 lg:py-12">
        <button
          onClick={() => router.push("/patients")}
          className="mb-6 inline-flex items-center gap-2 text-primary-600 hover:text-primary-700 font-medium transition-colors"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
          </svg>
          Back to Patients
        </button>

        <div className="mb-8 bg-white rounded-2xl card-shadow-lg p-6 lg:p-8">
          <div className="flex items-start justify-between gap-4 mb-4">
            <div className="flex-1">
              <h1 className="text-3xl lg:text-4xl font-bold text-slate-900 mb-2">
                {patient.first_name} {patient.last_name}
              </h1>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-sm text-slate-600">
                <div>
                  <span className="font-semibold text-slate-900">Age:</span> {calculateAge(patient.date_of_birth)}
                </div>
                <div>
                  <span className="font-semibold text-slate-900">Date of Birth:</span>{" "}
                  {new Date(patient.date_of_birth).toLocaleDateString()}
                </div>
                <div>
                  <span className="font-semibold text-slate-900">MRN:</span> {patient.medical_record_number || "N/A"}
                </div>
              </div>
            </div>
            <button
              onClick={() => router.push(`/cases/new?patient_id=${patient.id}`)}
              className="gradient-primary text-white px-6 py-3 rounded-xl font-semibold hover:shadow-lg transition-all flex items-center gap-2"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
              </svg>
              Add Scan
            </button>
          </div>
        </div>

        <div className="mb-6">
          <h2 className="text-2xl font-bold text-slate-900 mb-4">CT Scans ({cases.length})</h2>
          {cases.length === 0 ? (
            <div className="text-center py-12 bg-white/60 backdrop-blur-sm rounded-2xl border border-slate-200">
              <p className="text-slate-600 mb-2">No scans found for this patient</p>
              <button
                onClick={() => router.push(`/cases/new?patient_id=${patient.id}`)}
                className="gradient-primary text-white px-6 py-2 rounded-xl font-semibold hover:shadow-lg transition-all mt-4"
              >
                Upload First Scan
              </button>
            </div>
          ) : (
            <div className="grid gap-4 sm:gap-5">
              {cases.map((caseData) => (
                <CaseCard
                  key={caseData.id}
                  case={caseData}
                  onDelete={async () => {
                    await api.deleteCase(caseData.id);
                    await loadPatient();
                  }}
                  onView={(id) => router.push(`/cases/${id}`)}
                />
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

