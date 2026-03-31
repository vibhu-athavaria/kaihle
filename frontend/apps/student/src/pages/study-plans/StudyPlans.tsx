import { StudentLayout } from "@kaihle/ui";
import { useAuth } from "@kaihle/auth";
import { useStudentInfo } from "../../hooks/useStudentInfo";
import {
  useMyClasses,
  type StudentClassResponse,
} from "../../hooks/useMyClasses";

export function StudyPlans() {
  const { logout } = useAuth();
  const { data: studentInfo } = useStudentInfo();
  const { data: classesData } = useMyClasses();

  const firstName = studentInfo?.firstName ?? "";
  const lastName = studentInfo?.lastName ?? "";
  const studentName =
    [firstName, lastName].filter(Boolean).join(" ") || "Student";
  const gradeName = studentInfo?.gradeName ?? "";
  const curriculumName = studentInfo?.curriculumName ?? "";

  const sidebarClasses = (Array.isArray(classesData) ? classesData : []).map(
    (cls: StudentClassResponse) => ({
      id: cls.id,
      name: cls.name,
      subjectName: cls.subjectName,
      subjectId: cls.subjectId,
      diagnosticStatus: cls.onboardingDiagnosticStatus,
      diagnosticAttemptId: cls.diagnosticAttemptId,
    }),
  );

  return (
    <StudentLayout
      activeNav="study-plans"
      studentName={studentName}
      gradeName={gradeName}
      curriculumName={curriculumName}
      classes={sidebarClasses}
      onLogout={logout}
    >
      <div className="space-y-6">
        <h1 className="font-display font-bold text-2xl text-brand-ink">
          Study Plans
        </h1>
        <p className="text-brand-muted">
          Your study plans will appear here once your teacher assigns them.
        </p>
      </div>
    </StudentLayout>
  );
}
