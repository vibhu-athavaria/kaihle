/**
 * @jest-environment jsdom
 */
import { renderHook } from "@testing-library/react";
import { useStudentLayoutProps } from "../useStudentLayoutProps";

// Mock dependencies
jest.mock("@kaihle/auth", () => ({
  useAuth: jest.fn(() => ({ logout: jest.fn() })),
  apiClient: {
    get: jest.fn(),
  },
}));

jest.mock("../useStudentInfo", () => ({
  useStudentInfo: jest.fn(),
}));

jest.mock("../useMyClasses", () => ({
  useMyClasses: jest.fn(),
}));

jest.mock("../useStudentAssessments", () => ({
  useStudentAssessments: jest.fn(() => ({
    newCount: 0,
    isPending: false,
    isError: false,
  })),
}));

import { useAuth } from "@kaihle/auth";
import { useStudentInfo } from "../useStudentInfo";
import { useMyClasses } from "../useMyClasses";
import { useStudentAssessments } from "../useStudentAssessments";

const mockUseAuth = useAuth as jest.Mock;
const mockUseStudentInfo = useStudentInfo as jest.Mock;
const mockUseMyClasses = useMyClasses as jest.Mock;
const mockUseStudentAssessments = useStudentAssessments as jest.Mock;

describe("useStudentLayoutProps", () => {
  const mockLogout = jest.fn();

  beforeEach(() => {
    mockUseAuth.mockReturnValue({ logout: mockLogout });
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  it("test_useStudentLayoutProps_when_data_loaded_then_returns_formatted_student_name", () => {
    mockUseStudentInfo.mockReturnValue({
      data: {
        firstName: "Jane",
        lastName: "Doe",
        gradeName: "Grade 9",
        curriculumName: "Cambridge IGCSE",
      },
      isLoading: false,
    });
    mockUseMyClasses.mockReturnValue({ data: [], isLoading: false });

    const { result } = renderHook(() => useStudentLayoutProps());

    expect(result.current.studentName).toBe("Jane Doe");
  });

  it("test_useStudentLayoutProps_when_no_student_data_then_falls_back_to_student_string", () => {
    mockUseStudentInfo.mockReturnValue({ data: undefined, isLoading: false });
    mockUseMyClasses.mockReturnValue({ data: [], isLoading: false });

    const { result } = renderHook(() => useStudentLayoutProps());

    expect(result.current.studentName).toBe("Student");
  });

  it("test_useStudentLayoutProps_when_classes_loaded_then_maps_to_sidebar_shape", () => {
    mockUseStudentInfo.mockReturnValue({
      data: {
        firstName: "Jane",
        lastName: "Doe",
        gradeName: "Grade 9",
        curriculumName: "Cambridge IGCSE",
      },
      isLoading: false,
    });
    mockUseMyClasses.mockReturnValue({
      data: [
        {
          id: "cls-1",
          name: "Mathematics 9B",
          subjectName: "Mathematics",
          subjectId: "subj-1",
          onboardingDiagnosticStatus: "COMPLETED",
          diagnosticAttemptId: "attempt-1",
          gradeName: "Grade 9",
          teacherName: "Ms. Smith",
          curriculumId: "curr-1",
          academicYear: "2025-2026",
          isActive: true,
        },
      ],
      isLoading: false,
    });

    const { result } = renderHook(() => useStudentLayoutProps());

    expect(result.current.sidebarClasses).toHaveLength(1);
    expect(result.current.sidebarClasses[0]).toEqual({
      id: "cls-1",
      name: "Mathematics 9B",
      subjectName: "Mathematics",
      subjectId: "subj-1",
      teacherName: "Ms. Smith",
      diagnosticStatus: "COMPLETED",
      diagnosticAttemptId: "attempt-1",
    });
  });

  it("test_useStudentLayoutProps_when_either_loading_then_isLoading_is_true", () => {
    mockUseStudentInfo.mockReturnValue({ data: undefined, isLoading: true });
    mockUseMyClasses.mockReturnValue({ data: undefined, isLoading: false });

    const { result } = renderHook(() => useStudentLayoutProps());

    expect(result.current.isLoading).toBe(true);
  });

  it("test_useStudentLayoutProps_when_both_loaded_then_isLoading_is_false", () => {
    mockUseStudentInfo.mockReturnValue({
      data: {
        firstName: "Jane",
        lastName: "Doe",
        gradeName: "Grade 9",
        curriculumName: "Cambridge IGCSE",
      },
      isLoading: false,
    });
    mockUseMyClasses.mockReturnValue({ data: [], isLoading: false });

    const { result } = renderHook(() => useStudentLayoutProps());

    expect(result.current.isLoading).toBe(false);
  });

  it("test_useStudentLayoutProps_when_student_data_loaded_then_returns_studentId", () => {
    mockUseStudentInfo.mockReturnValue({
      data: {
        id: "stu-123",
        firstName: "Jane",
        lastName: "Doe",
        gradeName: "Grade 9",
        curriculumName: "Cambridge IGCSE",
        enrolledClasses: [],
      },
      isLoading: false,
    });
    mockUseMyClasses.mockReturnValue({ data: [], isLoading: false });
    mockUseStudentAssessments.mockReturnValue({
      newCount: 0,
      isPending: false,
      isError: false,
    });

    const { result } = renderHook(() => useStudentLayoutProps());
    expect(result.current.studentId).toBe("stu-123");
  });

  it("test_useStudentLayoutProps_when_student_has_new_assessments_then_returns_assessmentBadge", () => {
    mockUseStudentInfo.mockReturnValue({
      data: {
        id: "stu-1",
        firstName: "Jane",
        lastName: "Doe",
        gradeName: "Grade 9",
        curriculumName: "Cambridge IGCSE",
        enrolledClasses: [],
      },
      isLoading: false,
    });
    mockUseMyClasses.mockReturnValue({
      data: [],
      isLoading: false,
    });
    mockUseStudentAssessments.mockReturnValue({
      newCount: 3,
      isPending: false,
      isError: false,
    });

    const { result } = renderHook(() => useStudentLayoutProps());
    expect(result.current.assessmentBadge).toBe(3);
  });
});
