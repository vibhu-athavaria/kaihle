/**
 * Unit tests for EditStudentPanel.
 * Covers: grade select pre-populates correctly even when grades load after the panel opens.
 */
import "@testing-library/jest-dom";
import { render, screen, act } from "@testing-library/react";
import { EditStudentPanel } from "../EditStudentPanel";
import { useUpdateUser, useGrades } from "../../hooks/useSchoolAdmin";
import type { StudentProfile } from "../../hooks/useSchoolAdmin";

jest.mock("../../hooks/useSchoolAdmin");
jest.mock("@kaihle/ui", () => ({
  SlideOverPanel: ({
    children,
    open,
    footer,
  }: {
    children: React.ReactNode;
    open: boolean;
    footer: React.ReactNode;
  }) =>
    open ? (
      <div role="dialog">
        {children}
        {footer}
      </div>
    ) : null,
  Button: ({
    children,
    onClick,
    disabled,
    type,
    form,
  }: {
    children: React.ReactNode;
    onClick?: () => void;
    disabled?: boolean;
    type?: string;
    form?: string;
  }) => (
    <button
      onClick={onClick}
      disabled={disabled}
      type={type as "button" | "submit" | undefined}
      form={form}
    >
      {children}
    </button>
  ),
}));

const mockedUseUpdateUser = useUpdateUser as jest.MockedFunction<
  typeof useUpdateUser
>;
const mockedUseGrades = useGrades as jest.MockedFunction<typeof useGrades>;

const fakeStudent: StudentProfile = {
  id: "student-1",
  first_name: "Alice",
  last_name: "Wong",
  email: "alice@school.edu",
  is_active: true,
  grade_id: "grade-7-uuid",
  grade_level: 7,
  grade_name: "Grade 7",
  curriculum_name: "Cambridge Lower Secondary",
  enrolled_at: "2025-09-01",
  last_login_at: null,
  class_enrollments: [],
};

function renderPanel(gradesLoaded: boolean) {
  const grades = gradesLoaded
    ? [
        { id: "grade-6-uuid", level: 6 },
        { id: "grade-7-uuid", level: 7 },
        { id: "grade-8-uuid", level: 8 },
      ]
    : undefined;

  mockedUseGrades.mockReturnValue({
    data: grades,
    isLoading: !gradesLoaded,
  } as unknown as ReturnType<typeof useGrades>);

  mockedUseUpdateUser.mockReturnValue({
    mutateAsync: jest.fn(),
    isPending: false,
  } as unknown as ReturnType<typeof useUpdateUser>);

  return render(
    <EditStudentPanel open={true} onClose={jest.fn()} student={fakeStudent} />,
  );
}

describe("EditStudentPanel — grade field", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  test("test_edit_student_panel_when_grades_available_on_open_then_grade_select_shows_correct_grade", () => {
    renderPanel(true);

    const select = screen.getByRole("combobox", { name: /grade/i });
    expect(select).toHaveValue("grade-7-uuid");
  });

  test("test_edit_student_panel_when_grades_load_after_panel_opens_then_grade_select_syncs_to_correct_grade", async () => {
    mockedUseGrades.mockReturnValue({
      data: undefined,
      isLoading: true,
    } as unknown as ReturnType<typeof useGrades>);
    mockedUseUpdateUser.mockReturnValue({
      mutateAsync: jest.fn(),
      isPending: false,
    } as unknown as ReturnType<typeof useUpdateUser>);

    const { rerender } = render(
      <EditStudentPanel
        open={true}
        onClose={jest.fn()}
        student={fakeStudent}
      />,
    );

    // Grades load after initial render
    await act(async () => {
      mockedUseGrades.mockReturnValue({
        data: [
          { id: "grade-6-uuid", level: 6 },
          { id: "grade-7-uuid", level: 7 },
          { id: "grade-8-uuid", level: 8 },
        ],
        isLoading: false,
      } as unknown as ReturnType<typeof useGrades>);

      rerender(
        <EditStudentPanel
          open={true}
          onClose={jest.fn()}
          student={fakeStudent}
        />,
      );
    });

    const select = screen.getByRole("combobox", { name: /grade/i });
    expect(select).toHaveValue("grade-7-uuid");
  });
});
