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

  // Assessments are per-class; without a selected class we show an informational empty state.
  // Full multi-class assessment list is a future milestone feature.
  const hasClasses = sidebarClasses.length > 0;

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

        {!hasClasses ? (
          <div className="bg-white rounded-xl border border-brand-border p-12 text-center">
            <div className="text-4xl mb-4">📝</div>
            <h3 className="font-display font-bold text-xl text-brand-ink mb-2">
              No classes yet
            </h3>
            <p className="font-sans text-sm text-brand-body max-w-sm mx-auto">
              You will see your assessments once you are enrolled in a class.
            </p>
          </div>
        ) : (
          <div className="bg-white rounded-xl border border-brand-border p-12 text-center">
            <div className="text-4xl mb-4">✅</div>
            <h3 className="font-display font-bold text-xl text-brand-ink mb-2">
              No active assessments
            </h3>
            <p className="font-sans text-sm text-brand-body max-w-sm mx-auto">
              Your teacher will assign assessments here. Complete your class
              diagnostics first to unlock class content.
            </p>
          </div>
        )}
      </div>
    </StudentLayout>
  );
}
