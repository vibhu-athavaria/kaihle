/**
 * Unit tests for ClassManagement.
 * Covers: inactive toggle fetches inactive classes, active/inactive display.
 */
import "@testing-library/jest-dom";
import { render, screen, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { ClassManagement } from "../ClassManagement";
import { useSchoolClasses } from "../../hooks/useSchoolAdmin";

jest.mock("../../hooks/useSchoolAdmin");
jest.mock("../CreateClassModal", () => ({
  CreateClassModal: () => null,
}));
jest.mock("react-router-dom", () => ({
  ...jest.requireActual("react-router-dom"),
  useNavigate: () => jest.fn(),
}));

const mockedUseSchoolClasses = useSchoolClasses as jest.MockedFunction<
  typeof useSchoolClasses
>;

function makeClass(
  overrides: Partial<{
    id: string;
    name: string;
    is_active: boolean;
    subject_name: string;
    grade_name: string;
    teacher_name: string | null;
    has_teacher: boolean;
    avg_mastery: number | null;
    student_count: number;
    students_below_threshold: number;
    grade_level: number | null;
    teacher_id: string | null;
    diagnostic_status: "setup_needed" | "pending" | "has_data";
  }> = {},
) {
  return {
    id: "class-1",
    name: "Math 7A",
    is_active: true,
    subject_name: "Mathematics",
    grade_name: "Grade 7",
    teacher_name: "Ms. Rivera",
    has_teacher: true,
    avg_mastery: 0.75,
    student_count: 20,
    students_below_threshold: 2,
    grade_level: 7,
    teacher_id: "t1",
    diagnostic_status: "has_data" as const,
    ...overrides,
  };
}

function renderComponent() {
  return render(
    <MemoryRouter>
      <ClassManagement />
    </MemoryRouter>,
  );
}

describe("ClassManagement — inactive toggle", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  test("test_class_management_when_default_then_shows_active_classes", () => {
    mockedUseSchoolClasses.mockReturnValue({
      data: [makeClass({ name: "Math 7A", is_active: true })],
      isLoading: false,
      isError: false,
    } as unknown as ReturnType<typeof useSchoolClasses>);

    renderComponent();

    expect(mockedUseSchoolClasses).toHaveBeenCalledWith(true);
    expect(screen.getByText("Math 7A")).toBeInTheDocument();
  });

  test("test_class_management_when_inactive_toggle_clicked_then_hook_called_with_false", () => {
    mockedUseSchoolClasses.mockReturnValue({
      data: [],
      isLoading: false,
      isError: false,
    } as unknown as ReturnType<typeof useSchoolClasses>);

    renderComponent();

    const toggle = screen.getByRole("button", { name: /active|inactive/i });
    fireEvent.click(toggle);

    expect(mockedUseSchoolClasses).toHaveBeenCalledWith(false);
  });

  test("test_class_management_when_inactive_mode_then_displays_inactive_class", () => {
    mockedUseSchoolClasses
      .mockReturnValueOnce({
        data: [],
        isLoading: false,
        isError: false,
      } as unknown as ReturnType<typeof useSchoolClasses>)
      .mockReturnValue({
        data: [
          makeClass({
            name: "History 8A",
            is_active: false,
            diagnostic_status: "has_data",
          }),
        ],
        isLoading: false,
        isError: false,
      } as unknown as ReturnType<typeof useSchoolClasses>);

    renderComponent();
    const toggle = screen.getByRole("button", { name: /active|inactive/i });
    fireEvent.click(toggle);

    expect(screen.getByText("History 8A")).toBeInTheDocument();
  });
});
