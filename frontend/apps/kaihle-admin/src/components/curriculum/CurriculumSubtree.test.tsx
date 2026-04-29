import React from "react";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { CurriculumSubtree } from "./CurriculumSubtree";
import * as hooks from "../../hooks/useCurriculum";

jest.mock("../../hooks/useCurriculum", () => ({
  ...jest.requireActual("../../hooks/useCurriculum"),
  useGrades: jest.fn(),
  useSubjects: jest.fn(),
}));

const mockUseGrades = hooks.useGrades as jest.Mock;
const mockUseSubjects = hooks.useSubjects as jest.Mock;

const AS_LEVEL_ID = "as-level-id";
const LOWER_ID = "lower-id";

const ALL_GRADES = [
  { id: "g5", name: "Grade 5", level: 5, description: null, is_active: true },
  { id: "g6", name: "Grade 6", level: 6, description: null, is_active: true },
  {
    id: "g11",
    name: "Grade 11",
    level: 11,
    description: null,
    is_active: true,
  },
  {
    id: "g12",
    name: "Grade 12",
    level: 12,
    description: null,
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
  beforeEach(() => {
    mockUseSubjects.mockReturnValue({ data: [], isLoading: false });
  });

  test("shows only grades 11 and 12 under Cambridge AS Level, not grade 5 or 6", () => {
    mockUseGrades.mockImplementation((curriculumId?: string) => {
      if (curriculumId === AS_LEVEL_ID) {
        return {
          data: ALL_GRADES.filter((g) => g.level === 11 || g.level === 12),
          isLoading: false,
        };
      }
      return { data: ALL_GRADES, isLoading: false };
    });

    render(
      <CurriculumSubtree
        curriculumId={AS_LEVEL_ID}
        expandedNodes={new Set([AS_LEVEL_ID])}
        selectedNodeId={null}
        onToggleNode={noopHandler}
        onSelectNode={noopHandler}
        onEditGrade={noopHandler}
        onEditSubject={noopHandler}
        onLinkSubject={noopHandler}
        onOpenAddTopic={noopHandler}
        onUnlinkSubject={noopHandler}
      />,
      { wrapper },
    );

    expect(screen.getByText("Grade 11")).toBeInTheDocument();
    expect(screen.getByText("Grade 12")).toBeInTheDocument();
    expect(screen.queryByText("Grade 5")).not.toBeInTheDocument();
    expect(screen.queryByText("Grade 6")).not.toBeInTheDocument();
  });

  test("shows grades 6, 7, 8 under Cambridge Lower Secondary", () => {
    mockUseGrades.mockImplementation((curriculumId?: string) => {
      if (curriculumId === LOWER_ID) {
        return {
          data: ALL_GRADES.filter((g) => g.level >= 6 && g.level <= 8),
          isLoading: false,
        };
      }
      return { data: ALL_GRADES, isLoading: false };
    });

    render(
      <CurriculumSubtree
        curriculumId={LOWER_ID}
        expandedNodes={new Set([LOWER_ID])}
        selectedNodeId={null}
        onToggleNode={noopHandler}
        onSelectNode={noopHandler}
        onEditGrade={noopHandler}
        onEditSubject={noopHandler}
        onLinkSubject={noopHandler}
        onOpenAddTopic={noopHandler}
        onUnlinkSubject={noopHandler}
      />,
      { wrapper },
    );

    expect(screen.getByText("Grade 6")).toBeInTheDocument();
    expect(screen.queryByText("Grade 11")).not.toBeInTheDocument();
    expect(screen.queryByText("Grade 5")).not.toBeInTheDocument();
  });

  test("passes curriculumId to useGrades so filtering happens at API level", () => {
    mockUseGrades.mockReturnValue({ data: [], isLoading: false });

    render(
      <CurriculumSubtree
        curriculumId={AS_LEVEL_ID}
        expandedNodes={new Set([AS_LEVEL_ID])}
        selectedNodeId={null}
        onToggleNode={noopHandler}
        onSelectNode={noopHandler}
        onEditGrade={noopHandler}
        onEditSubject={noopHandler}
        onLinkSubject={noopHandler}
        onOpenAddTopic={noopHandler}
        onUnlinkSubject={noopHandler}
      />,
      { wrapper },
    );

    expect(mockUseGrades).toHaveBeenCalledWith(AS_LEVEL_ID);
  });
});
