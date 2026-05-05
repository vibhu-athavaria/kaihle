/**
 * Unit tests for ManageEnrollmentsModal.
 * Covers: grade-level filtering of available students.
 */
import "@testing-library/jest-dom";
import { render, screen } from "@testing-library/react";
import { ManageEnrollmentsModal } from "../ManageEnrollmentsModal";
import {
  useClassStudents,
  useSchoolStudents,
  useEnrollStudents,
  useUnenrollStudents,
} from "../../hooks/useSchoolAdmin";

jest.mock("../../hooks/useSchoolAdmin");
jest.mock("@kaihle/ui", () => ({
  Modal: ({
    children,
    open,
    title,
  }: {
    children: React.ReactNode;
    open: boolean;
    title: string;
  }) =>
    open ? (
      <div role="dialog" aria-label={title}>
        {children}
      </div>
    ) : null,
  Button: ({
    children,
    onClick,
    disabled,
  }: {
    children: React.ReactNode;
    onClick?: () => void;
    disabled?: boolean;
  }) => (
    <button onClick={onClick} disabled={disabled}>
      {children}
    </button>
  ),
}));

const mockedUseClassStudents = useClassStudents as jest.MockedFunction<
  typeof useClassStudents
>;
const mockedUseSchoolStudents = useSchoolStudents as jest.MockedFunction<
  typeof useSchoolStudents
>;
const mockedUseEnrollStudents = useEnrollStudents as jest.MockedFunction<
  typeof useEnrollStudents
>;
const mockedUseUnenrollStudents = useUnenrollStudents as jest.MockedFunction<
  typeof useUnenrollStudents
>;

function makeStudent(overrides: {
  id: string;
  first_name: string;
  last_name: string;
  grade_level: number | null;
}) {
  return {
    email: `${overrides.first_name.toLowerCase()}@school.edu`,
    is_active: true,
    last_login_at: null,
    worst_mastery: null,
    class_count: 0,
    needs_work_class_count: 0,
    diagnostic_completed: false,
    grade_name: overrides.grade_level ? `Grade ${overrides.grade_level}` : null,
    ...overrides,
  };
}

function renderModal(gradeLevel: number | null) {
  return render(
    <ManageEnrollmentsModal
      open={true}
      onOpenChange={jest.fn()}
      classId="class-1"
      className="Math 7A"
      gradeLevel={gradeLevel}
    />,
  );
}

describe("ManageEnrollmentsModal — grade filter", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockedUseClassStudents.mockReturnValue({
      data: [],
      isLoading: false,
    } as unknown as ReturnType<typeof useClassStudents>);
    mockedUseEnrollStudents.mockReturnValue({
      mutateAsync: jest.fn(),
    } as unknown as ReturnType<typeof useEnrollStudents>);
    mockedUseUnenrollStudents.mockReturnValue({
      mutateAsync: jest.fn(),
    } as unknown as ReturnType<typeof useUnenrollStudents>);
  });

  test("test_manage_enrollments_modal_when_grade_level_set_then_filters_out_wrong_grade_students", () => {
    mockedUseSchoolStudents.mockReturnValue({
      data: [
        makeStudent({
          id: "s1",
          first_name: "Alice",
          last_name: "Wong",
          grade_level: 7,
        }),
        makeStudent({
          id: "s2",
          first_name: "Bob",
          last_name: "Smith",
          grade_level: 8,
        }),
      ],
      isLoading: false,
    } as unknown as ReturnType<typeof useSchoolStudents>);

    renderModal(7);

    expect(screen.getByText("Alice Wong")).toBeInTheDocument();
    expect(screen.queryByText("Bob Smith")).not.toBeInTheDocument();
  });

  test("test_manage_enrollments_modal_when_grade_level_null_then_all_students_visible", () => {
    mockedUseSchoolStudents.mockReturnValue({
      data: [
        makeStudent({
          id: "s1",
          first_name: "Alice",
          last_name: "Wong",
          grade_level: 7,
        }),
        makeStudent({
          id: "s2",
          first_name: "Bob",
          last_name: "Smith",
          grade_level: 8,
        }),
      ],
      isLoading: false,
    } as unknown as ReturnType<typeof useSchoolStudents>);

    renderModal(null);

    expect(screen.getByText("Alice Wong")).toBeInTheDocument();
    expect(screen.getByText("Bob Smith")).toBeInTheDocument();
  });
});
