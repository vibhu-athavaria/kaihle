import { StudentLayout } from "@kaihle/ui";
import { useStudentLayoutProps } from "../../hooks/useStudentLayoutProps";
import { AccountSection } from "../../components/settings/AccountSection";
import { LearningProfileSection } from "../../components/settings/LearningProfileSection";
import { AccountActionsSection } from "../../components/settings/AccountActionsSection";

export function StudentSettings() {
  const layout = useStudentLayoutProps();

  return (
    <StudentLayout
      activeNav="home"
      studentName={layout.studentName}
      gradeName={layout.gradeName}
      curriculumName={layout.curriculumName}
      classes={layout.sidebarClasses}
      assessmentBadge={layout.assessmentBadge}
      onLogout={layout.onLogout}
    >
      <div className="max-w-xl mx-auto px-4 py-8">
        <h1 className="font-display font-bold text-2xl text-brand-ink mb-6">
          Settings
        </h1>
        <div className="space-y-4">
          <AccountSection />
          <LearningProfileSection />
          <AccountActionsSection />
        </div>
      </div>
    </StudentLayout>
  );
}
