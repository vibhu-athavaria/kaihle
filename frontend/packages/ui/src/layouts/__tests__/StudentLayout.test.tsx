import "@testing-library/jest-dom";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { StudentLayout } from "../StudentLayout";

const defaultProps = {
  activeNav: "home" as const,
  studentName: "Jane Doe",
  gradeName: "Grade 9",
  curriculumName: "Cambridge IGCSE",
  onLogout: jest.fn(),
};

function renderLayout(overrides = {}) {
  return render(
    <MemoryRouter>
      <StudentLayout {...defaultProps} {...overrides}>
        <div data-testid="children">Test Content</div>
      </StudentLayout>
    </MemoryRouter>,
  );
}

describe("StudentLayout", () => {
  it("renders children content", () => {
    renderLayout();
    expect(screen.getByTestId("children")).toBeInTheDocument();
  });

  it("renders sidebar with logo Kaihle", () => {
    renderLayout();
    expect(screen.getByText("Kaihle")).toBeInTheDocument();
  });

  it("renders LEARN navigation section", () => {
    renderLayout();
    expect(screen.getByText("Learn")).toBeInTheDocument();
  });

  it("renders nav items: Home, My progress, Study plans, Assessments", () => {
    renderLayout();
    expect(screen.getByText("Home")).toBeInTheDocument();
    expect(screen.getByText("My progress")).toBeInTheDocument();
    expect(screen.getByText("Study plans")).toBeInTheDocument();
    expect(screen.getByText("Assessments")).toBeInTheDocument();
  });

  it("renders profile card with student name and grade info", () => {
    renderLayout({
      studentName: "Jane Doe",
      gradeName: "Grade 9",
      curriculumName: "Cambridge IGCSE",
    });
    expect(screen.getByText("Jane Doe")).toBeInTheDocument();
    expect(screen.getByText(/Grade 9/)).toBeInTheDocument();
    expect(screen.getByText(/Cambridge IGCSE/)).toBeInTheDocument();
  });

  it("renders logout button", () => {
    renderLayout();
    expect(screen.getByText("Logout")).toBeInTheDocument();
  });

  it("calls onLogout when logout button is clicked", () => {
    const onLogout = jest.fn();
    renderLayout({ onLogout });
    screen.getByText("Logout").click();
    expect(onLogout).toHaveBeenCalledTimes(1);
  });

  it("renders classes section when classes prop is provided", () => {
    const classes = [
      {
        id: "cls-1",
        name: "Mathematics 9B",
        subjectName: "Mathematics",
        subjectId: "subj-1",
        diagnosticStatus: "COMPLETED" as const,
        diagnosticAttemptId: null,
      },
    ];
    renderLayout({ classes });
    expect(screen.getByText("Classes")).toBeInTheDocument();
    expect(screen.getByText("Mathematics 9B")).toBeInTheDocument();
  });

  it("renders active nav item with green dot indicator", () => {
    const { container } = renderLayout({ activeNav: "home" });
    const greenDot = container.querySelector(".bg-brand-primary");
    expect(greenDot).toBeInTheDocument();
  });

  it("renders avatar initials from studentName", () => {
    renderLayout({ studentName: "Jane Doe" });
    expect(screen.getByText("JD")).toBeInTheDocument();
  });

  it("handles single name for initials", () => {
    renderLayout({ studentName: "Madonna" });
    expect(screen.getByText("M")).toBeInTheDocument();
  });

  it("shows grade and curriculum in top nav subtitle", () => {
    const { container } = renderLayout({
      gradeName: "Grade 9",
      curriculumName: "Cambridge IGCSE",
    });
    expect(container.textContent).toContain("Grade 9");
    expect(container.textContent).toContain("Cambridge IGCSE");
  });

  it("renders locked class with Lock icon", () => {
    const classes = [
      {
        id: "cls-1",
        name: "Chemistry 10A",
        subjectName: "Chemistry",
        subjectId: "subj-2",
        diagnosticStatus: "PENDING" as const,
        diagnosticAttemptId: null,
      },
    ];
    renderLayout({ classes });
    expect(screen.getByText("Chemistry 10A")).toBeInTheDocument();
    expect(screen.getByLabelText(/Chemistry 10A/)).toBeInTheDocument();
  });
});
