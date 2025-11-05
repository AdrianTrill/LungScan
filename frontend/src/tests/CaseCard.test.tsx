/** Unit test for CaseCard component. */

import { render, screen } from "@testing-library/react";
import CaseCard from "@/components/cases/CaseCard";
import { Case } from "@/lib/types";

describe("CaseCard", () => {
  const mockCase: Case = {
    id: "test-case-1",
    filename: "test-scan.jpg",
    status: "pending",
    created_at: "2024-01-01T00:00:00Z",
    updated_at: "2024-01-01T00:00:00Z",
  };

  it("renders case information correctly", () => {
    const onDelete = jest.fn();
    const onView = jest.fn();

    render(<CaseCard case={mockCase} onDelete={onDelete} onView={onView} />);

    expect(screen.getByText("test-scan.jpg")).toBeInTheDocument();
    expect(screen.getByText("Pending")).toBeInTheDocument();
  });

  it("displays analyzed status badge", () => {
    const analyzedCase = { ...mockCase, status: "analyzed" as const };
    const onDelete = jest.fn();
    const onView = jest.fn();

    render(<CaseCard case={analyzedCase} onDelete={onDelete} onView={onView} />);

    expect(screen.getByText("Analyzed")).toBeInTheDocument();
  });
});

