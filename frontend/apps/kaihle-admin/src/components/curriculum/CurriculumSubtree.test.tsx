import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { CurriculumSubtree } from "./CurriculumSubtree";
import * as hooks from "../../hooks/useCurriculum";

jest.mock("../../hooks/useCurriculum", () => ({
  ...jest.requireActual("../../hooks/useCurriculum"),
  useSubjects: jest.fn(),
}));

const mockUseSubjects = hooks.useSubjects as jest.Mock;

const CURRICULUM_ID = "curr-igcse";

const SUBJECTS = [
  {
    id: "sub-math",
    name: "Mathematics",
    code: "MATH",
    description: null,
    icon: null,
    color: null,
    is_active: true,
  },
  {
    id: "sub-bio",
    name: "Biology",
    code: "BIO",
    description: null,
    icon: null,
    color: null,
    is_active: true,
  },
];

function wrapper({ children }: { children: React.ReactNode }) {
  return (
    <QueryClientProvider client={new QueryClient()}>
      {children}
    </QueryClientProvider>
  );
}

function noopHandler() {}

describe("CurriculumSubtree", () => {
  test("shows loading skeleton while subjects are loading", () => {
    mockUseSubjects.mockReturnValue({ data: [], isLoading: true });

    render(
      <CurriculumSubtree
        curriculumId={CURRICULUM_ID}
        selectedSubjectId={null}
        onSelectSubject={noopHandler}
        onEditSubject={noopHandler}
        onAddTopic={noopHandler}
        onUnlinkSubject={noopHandler}
      />,
      { wrapper },
    );

    expect(document.querySelector(".animate-pulse")).toBeInTheDocument();
  });

  test("renders subjects directly under curriculum without grade layer", () => {
    mockUseSubjects.mockReturnValue({ data: SUBJECTS, isLoading: false });

    render(
      <CurriculumSubtree
        curriculumId={CURRICULUM_ID}
        selectedSubjectId={null}
        onSelectSubject={noopHandler}
        onEditSubject={noopHandler}
        onAddTopic={noopHandler}
        onUnlinkSubject={noopHandler}
      />,
      { wrapper },
    );

    expect(screen.getByText("Mathematics")).toBeInTheDocument();
    expect(screen.getByText("Biology")).toBeInTheDocument();
  });

  test("does not show grade rows in the tree", () => {
    mockUseSubjects.mockReturnValue({ data: SUBJECTS, isLoading: false });

    render(
      <CurriculumSubtree
        curriculumId={CURRICULUM_ID}
        selectedSubjectId={null}
        onSelectSubject={noopHandler}
        onEditSubject={noopHandler}
        onAddTopic={noopHandler}
        onUnlinkSubject={noopHandler}
      />,
      { wrapper },
    );

    expect(screen.queryByText(/grade \d+/i)).not.toBeInTheDocument();
  });

  test("calls useSubjects with curriculumId so only linked subjects are shown", () => {
    mockUseSubjects.mockReturnValue({ data: [], isLoading: false });

    render(
      <CurriculumSubtree
        curriculumId={CURRICULUM_ID}
        selectedSubjectId={null}
        onSelectSubject={noopHandler}
        onEditSubject={noopHandler}
        onAddTopic={noopHandler}
        onUnlinkSubject={noopHandler}
      />,
      { wrapper },
    );

    expect(mockUseSubjects).toHaveBeenCalledWith(CURRICULUM_ID);
  });

  test("calls onSelectSubject with subject and curriculumId when subject row is clicked", () => {
    mockUseSubjects.mockReturnValue({ data: SUBJECTS, isLoading: false });
    const onSelectSubject = jest.fn();

    render(
      <CurriculumSubtree
        curriculumId={CURRICULUM_ID}
        selectedSubjectId={null}
        onSelectSubject={onSelectSubject}
        onEditSubject={noopHandler}
        onAddTopic={noopHandler}
        onUnlinkSubject={noopHandler}
      />,
      { wrapper },
    );

    fireEvent.click(screen.getByText("Mathematics"));

    expect(onSelectSubject).toHaveBeenCalledWith(
      expect.objectContaining({ id: "sub-math", curriculumId: CURRICULUM_ID }),
    );
  });

  test("highlights the currently selected subject", () => {
    mockUseSubjects.mockReturnValue({ data: SUBJECTS, isLoading: false });

    render(
      <CurriculumSubtree
        curriculumId={CURRICULUM_ID}
        selectedSubjectId="sub-math"
        onSelectSubject={noopHandler}
        onEditSubject={noopHandler}
        onAddTopic={noopHandler}
        onUnlinkSubject={noopHandler}
      />,
      { wrapper },
    );

    const mathRow = screen.getByText("Mathematics").closest("[data-selected]");
    expect(mathRow).toBeInTheDocument();
  });
});
