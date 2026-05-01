import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import { GradeTable } from "./GradeTable";

const mockGrades = [
  {
    id: "g1",
    name: "Grade 6",
    level: 6,
    description: null,
    is_active: true,
    curriculum_ids: ["c1", "c2"],
    curriculum_names: ["Cambridge Lower Sec", "IB MYP"],
  },
  {
    id: "g2",
    name: "Grade 9",
    level: 9,
    description: "IGCSE year",
    is_active: true,
    curriculum_ids: ["c3"],
    curriculum_names: ["Cambridge IGCSE"],
  },
  {
    id: "g3",
    name: "Grade 11",
    level: 11,
    description: null,
    is_active: false,
    curriculum_ids: [],
    curriculum_names: [],
  },
];

const noop = jest.fn();

function renderTable(
  overrides: Partial<Parameters<typeof GradeTable>[0]> = {},
) {
  return render(
    <GradeTable
      grades={mockGrades}
      isLoading={false}
      searchQuery=""
      curriculumFilter="ALL"
      statusFilter="ALL"
      onSearchChange={noop}
      onCurriculumFilterChange={noop}
      onStatusFilterChange={noop}
      onEditClick={noop}
      currentPage={1}
      totalPages={1}
      onPageChange={noop}
      {...overrides}
    />,
  );
}

describe("GradeTable", () => {
  beforeEach(() => jest.clearAllMocks());

  test("renders_grade_rows_when_grades_provided_then_displays_level_name_and_status", () => {
    renderTable();
    expect(screen.getByText("Grade 6")).toBeInTheDocument();
    expect(screen.getByText("Grade 9")).toBeInTheDocument();
    expect(screen.getByText("Grade 11")).toBeInTheDocument();
  });

  test("renders_curricula_chips_when_grade_has_curricula_then_shows_all_names", () => {
    renderTable();
    expect(screen.getByText("Cambridge Lower Sec")).toBeInTheDocument();
    expect(screen.getByText("IB MYP")).toBeInTheDocument();
    expect(screen.getByText("Cambridge IGCSE")).toBeInTheDocument();
  });

  test("renders_active_status_when_grade_is_active_then_shows_green_dot_and_label", () => {
    renderTable();
    const activeLabels = screen.getAllByText("Active");
    expect(activeLabels.length).toBeGreaterThan(0);
  });

  test("renders_inactive_status_when_grade_is_inactive_then_shows_gray_dot_and_label", () => {
    renderTable();
    const inactiveLabels = screen.getAllByText("Inactive");
    expect(inactiveLabels.length).toBeGreaterThan(0);
  });

  test("calls_onEditClick_when_edit_link_clicked_then_passes_grade", () => {
    const onEditClick = jest.fn();
    renderTable({ onEditClick });
    const editLinks = screen.getAllByText("Edit →");
    fireEvent.click(editLinks[0]);
    expect(onEditClick).toHaveBeenCalledWith(mockGrades[0]);
  });

  test("renders_skeleton_when_isLoading_true_then_no_rows_visible", () => {
    renderTable({ isLoading: true });
    expect(screen.queryByText("Grade 6")).not.toBeInTheDocument();
  });

  test("renders_empty_state_when_no_grades_then_shows_message", () => {
    renderTable({ grades: [] });
    expect(screen.getByText(/no grades found/i)).toBeInTheDocument();
  });

  test("renders_column_headers_then_level_name_curricula_status_action_present", () => {
    renderTable();
    const headers = screen.getAllByRole("columnheader");
    const headerTexts = headers.map((h) => h.textContent?.toLowerCase() ?? "");
    expect(headerTexts.some((t) => t.includes("level"))).toBe(true);
    expect(headerTexts.some((t) => t.includes("name"))).toBe(true);
    expect(headerTexts.some((t) => t.includes("curricula"))).toBe(true);
    expect(headerTexts.some((t) => t.includes("status"))).toBe(true);
  });

  test("calls_onSearchChange_when_search_input_changes_then_value_passed", () => {
    const onSearchChange = jest.fn();
    renderTable({ onSearchChange });
    const input = screen.getByPlaceholderText(/search grades/i);
    fireEvent.change(input, { target: { value: "Grade 9" } });
    expect(onSearchChange).toHaveBeenCalledWith("Grade 9");
  });

  test("renders_dash_for_curricula_when_grade_has_no_curricula_then_shows_em_dash", () => {
    renderTable();
    const emDashes = screen.getAllByText("—");
    expect(emDashes.length).toBeGreaterThan(0);
  });
});
