import { StudentLayout } from "@kaihle/ui";
import { useAuth } from "@kaihle/auth";
import { useStudentInfo } from "../../hooks/useStudentInfo";
import {
  useMyClasses,
  type StudentClassResponse,
} from "../../hooks/useMyClasses";
import { AccountSection } from "../../components/settings/AccountSection";
import { LearningProfileSection } from "../../components/settings/LearningProfileSection";
import { AccountActionsSection } from "../../components/settings/AccountActionsSection";

export function StudentSettings() {
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
      activeNav="home"
      studentName={studentName}
      gradeName={gradeName}
      curriculumName={curriculumName}
      classes={sidebarClasses}
      onLogout={logout}
    >
      <div className="max-w-xl mx-auto px-4 py-8">
        <h1 className="font-display text-2xl text-brand-ink mb-6">Settings</h1>
        <div className="space-y-4">
          <AccountSection />
          <LearningProfileSection />
          <AccountActionsSection />
        </div>
      </div>
    </StudentLayout>
  );
}
