import { useAuth } from "@kaihle/auth";
import { useStudentInfo } from "./useStudentInfo";
import { useMyClasses, type StudentClassResponse } from "./useMyClasses";
import { useStudentAssessments } from "./useStudentAssessments";

export interface SidebarClass {
  id: string;
  name: string;
  subjectName: string;
  subjectId: string;
  diagnosticStatus: "PENDING" | "IN_PROGRESS" | "COMPLETED";
  diagnosticAttemptId: string | null;
}

export interface StudentLayoutProps {
  studentName: string;
  gradeName: string;
  curriculumName: string;
  sidebarClasses: SidebarClass[];
  onLogout: () => void;
  isLoading: boolean;
  assessmentBadge: number;
  studentId: string | undefined;
}

/**
 * Consolidates repeated boilerplate across student pages:
 * student info + classes + auth + assessment badge count → StudentLayout props.
 *
 * Assessment badge count is derived here so every page automatically gets
 * the sidebar badge without additional API calls — React Query deduplicates
 * by query key, so the assessment queries are shared with the Assessments page cache.
 */
export function useStudentLayoutProps(): StudentLayoutProps {
  const { logout } = useAuth();
  const { data: studentInfo, isLoading: isInfoLoading } = useStudentInfo();
  const { data: classesData, isLoading: isClassesLoading } = useMyClasses();

  const classes = Array.isArray(classesData) ? classesData : [];

  const classIds = classes.map((cls: StudentClassResponse) => cls.id);

  const { newCount } = useStudentAssessments(classIds, studentInfo?.id);

  const firstName = studentInfo?.firstName ?? "";
  const lastName = studentInfo?.lastName ?? "";
  const studentName =
    [firstName, lastName].filter(Boolean).join(" ") || "Student";
  const gradeName = studentInfo?.gradeName ?? "";
  const curriculumName = studentInfo?.curriculumName ?? "";

  const sidebarClasses = classes.map(
    (cls: StudentClassResponse): SidebarClass => ({
      id: cls.id,
      name: cls.name,
      subjectName: cls.subjectName,
      subjectId: cls.subjectId,
      diagnosticStatus: cls.onboardingDiagnosticStatus,
      diagnosticAttemptId: cls.diagnosticAttemptId,
    }),
  );

  return {
    studentName,
    gradeName,
    curriculumName,
    sidebarClasses,
    onLogout: logout,
    isLoading: isInfoLoading || isClassesLoading,
    assessmentBadge: newCount,
    studentId: studentInfo?.id,
  };
}
