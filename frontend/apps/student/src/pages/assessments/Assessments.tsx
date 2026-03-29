import { StudentLayout } from "@kaihle/ui";
import { useAuth } from "@kaihle/auth";

export function Assessments() {
  const { logout } = useAuth();

  return (
    <StudentLayout activeNav="assessments" onLogout={logout}>
      <div className="space-y-6">
        <h1 className="font-display font-bold text-2xl text-brand-ink">
          Assessments
        </h1>
        <p className="text-brand-muted">
          Your assessments will appear here once your teacher assigns them.
        </p>
      </div>
    </StudentLayout>
  );
}
