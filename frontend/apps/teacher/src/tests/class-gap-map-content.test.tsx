import "@testing-library/jest-dom";
import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { ClassGapMapContent } from "../components/gap-map/ClassGapMapContent";

// ── Shared fixtures ───────────────────────────────────────────────────────────

const GRADE_8_ID = "grade-8-id";
const GRADE_9_ID = "grade-9-id";
const TOPIC_ALGEBRA_ID = "topic-algebra";
const TOPIC_CHEM_ID = "topic-chem";
const SUBTOPIC_LINEAR_ID = "sub-linear";
const SUBTOPIC_ACIDS_ID = "sub-acids";
const STUDENT_1_ID = "student-1";
const STUDENT_2_ID = "student-2";

const MOCK_GAP_MAP = {
  class_id: "cls-1",
  subject_id: "sub-1",
  generated_at: "2026-05-01T00:00:00Z",
  has_student_data: true,
  nodes: [
    {
      subtopic_id: SUBTOPIC_LINEAR_ID,
      subtopic_name: "Linear Equations",
      topic_id: TOPIC_ALGEBRA_ID,
      topic_name: "Algebra",
      grade_id: GRADE_8_ID,
      grade_name: "Grade 8",
      grade_level: 8,
      class_average: 0.65,
      student_count: 2,
      student_scores: [
        {
          student_id: STUDENT_1_ID,
          student_name: "Alice Smith",
          mastery_score: 0.7,
          confidence: 0.8, // well-evidenced — renders confident
          last_assessed_at: null,
        },
        {
          student_id: STUDENT_2_ID,
          student_name: "Bob Jones",
          mastery_score: 0.6,
          confidence: 0.2, // thin evidence — renders provisional
          last_assessed_at: null,
        },
      ],
    },
    {
      subtopic_id: SUBTOPIC_ACIDS_ID,
      subtopic_name: "Acids and Bases",
      topic_id: TOPIC_CHEM_ID,
      topic_name: "Chemistry Basics",
      grade_id: GRADE_9_ID,
      grade_name: "Grade 9",
      grade_level: 9,
      class_average: 0.3,
      student_count: 2,
      student_scores: [
        {
          student_id: STUDENT_1_ID,
          student_name: "Alice Smith",
          mastery_score: 0.35,
          last_assessed_at: null,
        },
        {
          student_id: STUDENT_2_ID,
          student_name: "Bob Jones",
          mastery_score: 0.25,
          last_assessed_at: null,
        },
      ],
    },
  ],
};

// ── Module mocks ──────────────────────────────────────────────────────────────

jest.mock("../hooks/useClassGapMap", () => ({
  useClassGapMap: jest.fn(),
}));
jest.mock("../hooks/useClass", () => ({
  useClass: jest.fn(),
}));
jest.mock("../hooks/useClassAssessments", () => ({
  useClassAssessments: jest.fn(),
}));
jest.mock("../hooks/useClassEnrollments", () => ({
  useClassEnrollments: jest.fn(),
}));
jest.mock("../components/gap-map/LearningProfileSidePanel", () => ({
  LearningProfileSidePanel: () => null,
}));

import { useClassGapMap } from "../hooks/useClassGapMap";
import { useClass } from "../hooks/useClass";
import { useClassAssessments } from "../hooks/useClassAssessments";
import { useClassEnrollments } from "../hooks/useClassEnrollments";

const mockUseClassGapMap = useClassGapMap as jest.Mock;
const mockUseClass = useClass as jest.Mock;
const mockUseClassAssessments = useClassAssessments as jest.Mock;
const mockUseClassEnrollments = useClassEnrollments as jest.Mock;

function setup() {
  mockUseClass.mockReturnValue({
    data: {
      name: "Year 9 Chemistry",
      subject_id: "sub-1",
      subject_name: "Chemistry",
    },
  });
  mockUseClassAssessments.mockReturnValue({
    data: [{ assessment_type: "DIAGNOSTIC" }],
  });
  mockUseClassEnrollments.mockReturnValue({
    data: [{ diagnostic_completed: true }, { diagnostic_completed: true }],
  });
  mockUseClassGapMap.mockReturnValue({
    data: MOCK_GAP_MAP,
    isLoading: false,
    isError: false,
  });
}

function renderComponent(classId = "cls-1") {
  return render(
    <MemoryRouter>
      <ClassGapMapContent classId={classId} showExport={false} />
    </MemoryRouter>,
  );
}

// ── Tests ─────────────────────────────────────────────────────────────────────

describe("ClassGapMapContent — expand/collapse", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    setup();
  });

  test("test_gap_map_when_loaded_then_grade_headers_are_visible", () => {
    renderComponent();
    expect(screen.getByText("Grade 8")).toBeInTheDocument();
    expect(screen.getByText("Grade 9")).toBeInTheDocument();
  });

  test("test_gap_map_when_loaded_then_topic_headers_are_visible", () => {
    renderComponent();
    expect(screen.getByText("Algebra")).toBeInTheDocument();
    expect(screen.getByText("Chemistry Basics")).toBeInTheDocument();
  });

  test("test_gap_map_when_loaded_then_topics_with_mastery_data_are_open_by_default", () => {
    renderComponent();
    // Both topics have mastery data — subtopics visible without any interaction
    expect(screen.getByText("Linear Equations")).toBeInTheDocument();
    expect(screen.getByText("Acids and Bases")).toBeInTheDocument();
  });

  test("test_gap_map_when_topic_has_no_mastery_data_then_it_is_closed_by_default", () => {
    mockUseClassGapMap.mockReturnValue({
      data: {
        ...MOCK_GAP_MAP,
        nodes: [
          {
            ...MOCK_GAP_MAP.nodes[0],
            class_average: null,
            student_scores: MOCK_GAP_MAP.nodes[0].student_scores.map((s) => ({
              ...s,
              mastery_score: null,
            })),
          },
        ],
      },
      isLoading: false,
      isError: false,
    });
    renderComponent();
    // Topic has no mastery data — subtopic hidden by default
    expect(screen.queryByText("Linear Equations")).not.toBeInTheDocument();
    expect(screen.getByText("Algebra")).toBeInTheDocument();
  });

  test("test_gap_map_when_topic_clicked_then_it_collapses", () => {
    renderComponent();
    // Topic starts open (has mastery data)
    expect(screen.getByText("Linear Equations")).toBeInTheDocument();
    fireEvent.click(screen.getByText("Algebra"));
    expect(screen.queryByText("Linear Equations")).not.toBeInTheDocument();
  });

  test("test_gap_map_when_topic_clicked_twice_then_subtopic_rows_visible_again", () => {
    renderComponent();
    const algebraHeader = screen.getByText("Algebra");
    fireEvent.click(algebraHeader); // collapse
    expect(screen.queryByText("Linear Equations")).not.toBeInTheDocument();
    fireEvent.click(algebraHeader); // re-expand
    expect(screen.getByText("Linear Equations")).toBeInTheDocument();
  });

  test("test_gap_map_when_grade_collapsed_then_topics_and_subtopics_hidden", () => {
    renderComponent();
    // Topics start open — subtopics visible
    expect(screen.getByText("Linear Equations")).toBeInTheDocument();

    // Collapse the grade — should hide topics and subtopics
    fireEvent.click(screen.getByText("Grade 8"));
    expect(screen.queryByText("Algebra")).not.toBeInTheDocument();
    expect(screen.queryByText("Linear Equations")).not.toBeInTheDocument();
  });

  test("test_gap_map_when_grade_collapsed_and_reopened_then_subtopics_visible_again", () => {
    renderComponent();
    const grade8Header = screen.getByText("Grade 8");
    fireEvent.click(grade8Header); // collapse
    fireEvent.click(grade8Header); // re-open

    expect(screen.getByText("Algebra")).toBeInTheDocument();
    // Topic was open before collapse, state is preserved — subtopics visible
    expect(screen.getByText("Linear Equations")).toBeInTheDocument();
  });

  test("test_gap_map_when_has_no_student_data_then_empty_state_shown", () => {
    mockUseClassGapMap.mockReturnValue({
      data: { ...MOCK_GAP_MAP, has_student_data: false },
      isLoading: false,
      isError: false,
    });
    mockUseClassAssessments.mockReturnValue({
      data: [{ assessment_type: "DIAGNOSTIC" }],
    });
    renderComponent();
    expect(screen.getByText(/Waiting for students/i)).toBeInTheDocument();
  });

  test("test_gap_map_when_loading_then_skeleton_shown", () => {
    mockUseClassGapMap.mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
    });
    const { container } = renderComponent();
    expect(container.querySelector(".animate-pulse")).toBeInTheDocument();
  });
});

describe("ClassGapMapContent — provisional evidence (MLH-T6)", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    setup();
  });

  test("test_gap_map_legend_when_rendered_then_includes_provisional_entry", () => {
    // Uncertainty is a legend entry in its own right. Without it a dashed cell is an
    // unexplained visual difference rather than a signal a teacher can act on.
    renderComponent();
    expect(
      screen.getByText(/Dashed outline — provisional/i),
    ).toBeInTheDocument();
  });

  test("test_gap_map_legend_when_rendered_then_mastery_bands_still_present", () => {
    // T6 is additive; the three display bands are explicitly out of scope.
    renderComponent();
    // getAllByText, not getByText: these labels appear in the legend AND inside cells,
    // which is the point — the legend explains what the cells already show.
    for (const band of ["Strong", "Developing", "Needs Work", "Not assessed"]) {
      expect(screen.getAllByText(band).length).toBeGreaterThan(0);
    }
  });

  // The three below exercise the path a teacher actually sees — HeatCell inside the
  // shared ClassGapMapTable. The packages/ui unit tests cover GapMapCell, which only
  // school-admin renders; without these the shipped provisional branch had no coverage.

  test("test_gap_map_when_score_has_thin_evidence_then_cell_marked_provisional", () => {
    renderComponent();
    expect(screen.getAllByLabelText(/provisional/i).length).toBeGreaterThan(0);
  });

  test("test_gap_map_when_score_well_evidenced_then_cell_not_marked_provisional", () => {
    renderComponent();
    const confident = screen.getByLabelText(/Alice Smith.*Linear Equations/i);
    expect(confident.getAttribute("aria-label")).not.toContain("provisional");
  });

  test("test_gap_map_when_cell_confident_then_aria_label_still_carries_mastery_and_score", () => {
    // aria-label OVERRIDES inner text for screen readers, so a confident cell must still
    // announce its band and score — state is never conveyed by colour alone
    // (DESIGN_SYSTEM §9.1).
    renderComponent();
    const label =
      screen
        .getByLabelText(/Alice Smith.*Linear Equations/i)
        .getAttribute("aria-label") ?? "";
    expect(label).toMatch(/Strong|Developing|Needs Work/);
    expect(label).toMatch(/\d+%/);
  });
});
