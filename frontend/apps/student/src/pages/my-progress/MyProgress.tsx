import { StudentLayout } from "@kaihle/ui";
import { useAuth } from "@kaihle/auth";

export function MyProgress() {
  const { logout } = useAuth();

  return (
    <StudentLayout activeNav="progress" onLogout={logout}>
      <div className="space-y-6">
        <h1 className="font-display font-bold text-2xl text-brand-ink">
          My Progress
        </h1>
        <p className="text-brand-muted">
          Your learning progress will appear here once you complete assessments.
        </p>
      </div>
    </StudentLayout>
  );
}
