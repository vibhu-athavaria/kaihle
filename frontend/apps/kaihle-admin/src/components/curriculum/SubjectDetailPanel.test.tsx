import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { SubjectDetailPanel } from "./SubjectDetailPanel";
import * as hooks from "../../hooks/useCurriculum";

jest.mock("../../hooks/useCurriculum", () => ({
  ...jest.requireActual("../../hooks/useCurriculum"),
  useTopics: jest.fn(),
  useSubtopics: jest.fn(),
}));

const mockUseTopics = hooks.useTopics as jest.Mock;
const mockUseSubtopics = hooks.useSubtopics as jest.Mock;

const SUBJECT_ID = "sub-math";
const CURRICULUM_ID = "curr-igcse";
const GRADE_ID = "grade-9";

const TOPICS = [
  {
    curriculum_topic_id: "ct-1",
    topic_id: "t-1",
    name: "Algebra",
    canonical_code: "MATH.ALG",
    standard_code: null,
    sequence_order: 1,
    learning_objectives: [],
    recommended_weeks: 4,
    is_required: true,
    is_active: true,
    subtopic_count: 2,
  },
  {
    curriculum_topic_id: "ct-2",
    topic_id: "t-2",
    name: "Geometry",
    canonical_code: "MATH.GEO",
    standard_code: null,
    sequence_order: 2,
    learning_objectives: [],
    recommended_weeks: 3,
    is_required: true,
    is_active: true,
    subtopic_count: 1,
  },
];

const SUBTOPICS = [
  {
    id: "st-1",
    curriculum_topic_id: "ct-1",
    name: "Linear equations",
    canonical_code: "MATH.ALG.1",
    learning_objective: "Solve linear equations",
    description: null,
    keywords: [],
    bloom_taxonomy_level: "apply",
    difficulty_level: 2,
    estimated_minutes: 45,
    sequence_order: 1,
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

describe("SubjectDetailPanel", () => {
  beforeEach(() => {
    mockUseSubtopics.mockReturnValue({ data: [], isLoading: false });
  });

  test("shows skeleton while topics are loading", () => {
    mockUseTopics.mockReturnValue({ data: [], isLoading: true });

    render(
      <SubjectDetailPanel
        subjectId={SUBJECT_ID}
        subjectName="Mathematics"
        curriculumId={CURRICULUM_ID}
        gradeId={GRADE_ID}
        onAddTopic={() => {}}
        onEditTopic={() => {}}
        onAddSubtopic={() => {}}
        onEditSubtopic={() => {}}
      />,
      { wrapper },
    );

    expect(document.querySelector(".animate-pulse")).toBeInTheDocument();
    expect(screen.queryByText("Algebra")).not.toBeInTheDocument();
  });

  test("shows empty state when subject has no topics", () => {
    mockUseTopics.mockReturnValue({ data: [], isLoading: false });

    render(
      <SubjectDetailPanel
        subjectId={SUBJECT_ID}
        subjectName="Mathematics"
        curriculumId={CURRICULUM_ID}
        gradeId={GRADE_ID}
        onAddTopic={() => {}}
        onEditTopic={() => {}}
        onAddSubtopic={() => {}}
        onEditSubtopic={() => {}}
      />,
      { wrapper },
    );

    expect(screen.getByText(/no topics yet/i)).toBeInTheDocument();
  });

  test("renders topic list for the selected subject", () => {
    mockUseTopics.mockReturnValue({ data: TOPICS, isLoading: false });

    render(
      <SubjectDetailPanel
        subjectId={SUBJECT_ID}
        subjectName="Mathematics"
        curriculumId={CURRICULUM_ID}
        gradeId={GRADE_ID}
        onAddTopic={() => {}}
        onEditTopic={() => {}}
        onAddSubtopic={() => {}}
        onEditSubtopic={() => {}}
      />,
      { wrapper },
    );

    expect(screen.getByText("Algebra")).toBeInTheDocument();
    expect(screen.getByText("Geometry")).toBeInTheDocument();
  });

  test("calls useTopics with correct subjectId, curriculumId and gradeId", () => {
    mockUseTopics.mockReturnValue({ data: [], isLoading: false });

    render(
      <SubjectDetailPanel
        subjectId={SUBJECT_ID}
        subjectName="Mathematics"
        curriculumId={CURRICULUM_ID}
        gradeId={GRADE_ID}
        onAddTopic={() => {}}
        onEditTopic={() => {}}
        onAddSubtopic={() => {}}
        onEditSubtopic={() => {}}
      />,
      { wrapper },
    );

    expect(mockUseTopics).toHaveBeenCalledWith(
      SUBJECT_ID,
      CURRICULUM_ID,
      GRADE_ID,
    );
  });

  test("expands a topic to show its subtopics on click", () => {
    mockUseTopics.mockReturnValue({ data: TOPICS, isLoading: false });
    mockUseSubtopics.mockImplementation((topicId: string) => {
      if (topicId === "t-1") return { data: SUBTOPICS, isLoading: false };
      return { data: [], isLoading: false };
    });

    render(
      <SubjectDetailPanel
        subjectId={SUBJECT_ID}
        subjectName="Mathematics"
        curriculumId={CURRICULUM_ID}
        gradeId={GRADE_ID}
        onAddTopic={() => {}}
        onEditTopic={() => {}}
        onAddSubtopic={() => {}}
        onEditSubtopic={() => {}}
      />,
      { wrapper },
    );

    // Subtopics not visible before expand
    expect(screen.queryByText("Linear equations")).not.toBeInTheDocument();

    // Click the Algebra row to expand
    fireEvent.click(screen.getByText("Algebra"));

    expect(screen.getByText("Linear equations")).toBeInTheDocument();
  });

  test("calls onAddTopic when Add Topic button is clicked", () => {
    mockUseTopics.mockReturnValue({ data: [], isLoading: false });
    const onAddTopic = jest.fn();

    render(
      <SubjectDetailPanel
        subjectId={SUBJECT_ID}
        subjectName="Mathematics"
        curriculumId={CURRICULUM_ID}
        gradeId={GRADE_ID}
        onAddTopic={onAddTopic}
        onEditTopic={() => {}}
        onAddSubtopic={() => {}}
        onEditSubtopic={() => {}}
      />,
      { wrapper },
    );

    fireEvent.click(screen.getByTitle("Add topic"));
    expect(onAddTopic).toHaveBeenCalledTimes(1);
  });
});
