import { Link } from "react-router-dom";
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

  // Determine which empty state to show based on diagnostic completion
  const hasDiagnosticComplete = sidebarClasses.some(
    (cls) => cls.diagnosticStatus === "COMPLETED",
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

        {hasDiagnosticComplete ? (
          <div className="bg-white rounded-xl border border-brand-border p-12 text-center">
            <h3 className="font-display font-bold text-xl text-brand-ink mb-2">
              Plans are being generated
            </h3>
            <p className="font-sans text-sm text-brand-muted max-w-sm mx-auto mb-4">
              Your study plans are being built from your assessment results.
              They'll appear here soon — in the meantime, explore your progress
              to see where to focus.
            </p>
            <Link
              to="/student/my-progress"
              className="font-sans text-sm font-semibold text-brand-primary hover:text-brand-dark focus-visible:ring-2 focus-visible:ring-brand-primary rounded"
            >
              View my progress →
            </Link>
          </div>
        ) : (
          <div className="bg-white rounded-xl border border-brand-border p-12 text-center">
            <h3 className="font-display font-bold text-xl text-brand-ink mb-2">
              No study plans yet
            </h3>
            <p className="font-sans text-sm text-brand-muted max-w-sm mx-auto mb-4">
              Study plans are built automatically from your assessment results —
              personalised to the specific topics where you have gaps. Complete
              your first assessment to unlock them.
            </p>
            <Link
              to="/student/assessments"
              className="font-sans text-sm font-semibold text-brand-primary hover:text-brand-dark focus-visible:ring-2 focus-visible:ring-brand-primary rounded"
            >
              View your assessments →
            </Link>
          </div>
        )}
      </div>
    </StudentLayout>
  );
}
