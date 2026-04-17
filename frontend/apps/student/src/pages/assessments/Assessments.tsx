import { Link } from "react-router-dom";
import { StudentLayout } from "@kaihle/ui";
import { useAuth } from "@kaihle/auth";
import { useStudentInfo } from "../../hooks/useStudentInfo";
import {
  useMyClasses,
  type StudentClassResponse,
} from "../../hooks/useMyClasses";

export function Assessments() {
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

  // Two-state empty state: no diagnostic attempt vs diagnostic exists but no teacher assessments
  const hasDiagnosticAttempt = sidebarClasses.some(
    (cls) => cls.diagnosticAttemptId != null,
  );

  return (
    <StudentLayout
      activeNav="assessments"
      studentName={studentName}
      gradeName={gradeName}
      curriculumName={curriculumName}
      classes={sidebarClasses}
      onLogout={logout}
    >
      <div className="space-y-6">
        <h1 className="font-display font-bold text-2xl text-brand-ink">
          Assessments
        </h1>

        {hasDiagnosticAttempt ? (
          <div className="bg-white rounded-xl border border-brand-border p-12 text-center">
            <h3 className="font-display font-bold text-xl text-brand-ink mb-2">
              No active assessments
            </h3>
            <p className="font-sans text-sm text-brand-muted max-w-sm mx-auto mb-4">
              No assessments assigned yet. Your teacher will share them here
              when ready.
            </p>
            <Link
              to="/student/my-progress"
              className="font-sans text-sm font-semibold text-brand-primary hover:text-brand-dark focus-visible:ring-2 focus-visible:ring-brand-primary rounded"
            >
              See your progress so far →
            </Link>
          </div>
        ) : (
          <div className="bg-white rounded-xl border border-brand-border p-12 text-center">
            <h3 className="font-display font-bold text-xl text-brand-ink mb-2">
              No assessments yet
            </h3>
            <p className="font-sans text-sm text-brand-muted max-w-sm mx-auto">
              Your teacher will assign assessments here once you are enrolled.
              These help build your personalised gap map so Kaihle knows exactly
              where to focus.
            </p>
          </div>
        )}
      </div>
    </StudentLayout>
  );
}
