import { StudentLayout } from "@kaihle/ui";
import { useAuth } from "@kaihle/auth";
import { AccountSection } from "../../components/settings/AccountSection";
import { LearningProfileSection } from "../../components/settings/LearningProfileSection";
import { AccountActionsSection } from "../../components/settings/AccountActionsSection";

export function StudentSettings() {
  const { logout } = useAuth();

  return (
    <StudentLayout onLogout={logout}>
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
