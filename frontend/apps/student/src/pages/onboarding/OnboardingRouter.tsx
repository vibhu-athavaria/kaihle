import { Navigate } from "react-router-dom";
import { useOnboardingStatus } from "../../hooks/useOnboardingStatus";

export function OnboardingRouter() {
  const { status, isLoading } = useOnboardingStatus();

  if (isLoading || !status) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-primary" />
      </div>
    );
  }

  // Check if all diagnostics are completed
  const diagnosticsComplete =
    status.diagnostics_by_class?.every((d) => d.status === "COMPLETED") ??
    false;

  // If no diagnostics yet (empty array), treat as not complete
  const hasDiagnostics = (status.diagnostics_by_class?.length ?? 0) > 0;
  const allDiagnosticsComplete = hasDiagnostics && diagnosticsComplete;

  if (!status.learning_profile_complete) {
    return <Navigate to="/student/onboarding/profile" replace />;
  }

  // If diagnostics exist and all complete, go to dashboard
  if (hasDiagnostics && allDiagnosticsComplete) {
    return <Navigate to="/student/dashboard" replace />;
  }

  // If learning profile complete but diagnostics not, go to diagnostics
  if (status.learning_profile_complete && !allDiagnosticsComplete) {
    return <Navigate to="/student/onboarding/diagnostics" replace />;
  }

  return <Navigate to="/student/onboarding/profile" replace />;
}
