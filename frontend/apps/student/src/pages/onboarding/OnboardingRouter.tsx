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

  if (status.overall === "COMPLETED") {
    return <Navigate to="/student/dashboard" replace />;
  }

  if (!status.learning_profile_complete) {
    return <Navigate to="/student/onboarding/profile" replace />;
  }

  if (status.learning_profile_complete && !status.diagnostics_complete) {
    return <Navigate to="/student/onboarding/diagnostics" replace />;
  }

  return <Navigate to="/student/onboarding/profile" replace />;
}
