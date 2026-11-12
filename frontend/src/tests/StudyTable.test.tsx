import { render, screen } from "@testing-library/react";
import StudyTable from "@/components/studies/StudyTable";
import type { Case, Patient } from "@/lib/types";

jest.mock("next/navigation", () => ({ useRouter: () => ({ push: jest.fn() }) }));
// Thumbnails load their images asynchronously; that is not what these tests are about.
jest.mock("@/lib/api", () => ({ api: { imageUrl: () => new Promise(() => undefined) } }));

const base: Case = {
  id: "sample-07",
  filename: "slice-000158.png",
  patient_id: "patient-001",
  status: "analyzed",
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
  cancer_probability: 0.351212,
  flagged: false,
  dataset_label: "adenocarcinoma",
};

const patients = new Map<string, Patient>([
  [
    "patient-001",
    {
      id: "patient-001",
      first_name: "John",
      last_name: "Smith",
      date_of_birth: "1975-03-15",
      medical_record_number: "MRN-2024-001",
      created_at: "2026-01-01T00:00:00Z",
    },
  ],
]);

describe("StudyTable", () => {
  beforeAll(() => {
    Element.prototype.scrollIntoView = jest.fn();
  });

  it("shows each study's patient, read, and label", () => {
    const pending: Case = {
      ...base,
      id: "c2",
      filename: "upload.png",
      patient_id: null,
      status: "pending",
      cancer_probability: null,
      flagged: null,
      dataset_label: null,
    };
    render(
      <StudyTable
        studies={[base, pending]}
        patients={patients}
        selected={0}
        onSelect={() => undefined}
      />
    );
    expect(screen.getAllByTestId("study-row")).toHaveLength(2);
    expect(screen.getByText("slice-000158.png")).toBeInTheDocument();
    expect(screen.getByText("John Smith")).toBeInTheDocument();
    expect(screen.getByText("35.1%")).toBeInTheDocument();
    expect(screen.getByText("Cleared")).toBeInTheDocument();
    expect(screen.getByText("Awaiting read")).toBeInTheDocument();
    expect(screen.getByText("Unassigned")).toBeInTheDocument();
    expect(screen.getByText("Adeno")).toBeInTheDocument();
  });

  it("leaves out the patient column on a patient's page", () => {
    render(<StudyTable studies={[base]} patients={null} selected={0} onSelect={() => undefined} />);
    expect(screen.queryByText("Patient")).not.toBeInTheDocument();
    expect(screen.queryByText("John Smith")).not.toBeInTheDocument();
  });
});
