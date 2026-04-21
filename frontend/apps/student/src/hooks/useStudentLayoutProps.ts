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
  assessmentBadgeCount: number;
}

export function useStudentLayoutProps(): StudentLayoutProps {
  const { logout } = useAuth();
  const { data: studentInfo, isLoading: isInfoLoading } = useStudentInfo();
  const { data: classesData, isLoading: isClassesLoading } = useMyClasses();

  const classIds = (Array.isArray(classesData) ? classesData : []).map(
    (cls: StudentClassResponse) => cls.id,
  );

  const { newCount } = useStudentAssessments(classIds, studentInfo?.id);

  const firstName = studentInfo?.firstName ?? "";
  const lastName = studentInfo?.lastName ?? "";
  const studentName =
    [firstName, lastName].filter(Boolean).join(" ") || "Student";
  const gradeName = studentInfo?.gradeName ?? "";
  const curriculumName = studentInfo?.curriculumName ?? "";

  const sidebarClasses = (Array.isArray(classesData) ? classesData : []).map(
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
    assessmentBadgeCount: newCount,
  };
}
