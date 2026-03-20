import { Navigate } from "react-router-dom";
import { useOnboardingStatus } from "../../hooks/useOnboardingStatus";

/**
 * Check if all onboarding steps are complete:
 * - learning_profile_complete must be true
 * - ALL diagnostics_by_class must have status COMPLETED
 */
function isOnboardingComplete(status: {
  learning_profile_complete: boolean;
  diagnostics_by_class?: Array<{ status: string }>;
}): boolean {
  if (!status.learning_profile_complete) return false;
  if (!status.diagnostics_by_class || status.diagnostics_by_class.length === 0)
    return false;
  return status.diagnostics_by_class.every((d) => d.status === "COMPLETED");
}

export function OnboardingRouter() {
  const { status, isLoading } = useOnboardingStatus();

  if (isLoading || !status) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-primary" />
      </div>
    );
  }

  // If onboarding is fully complete (learning profile + all diagnostics), go to dashboard
  if (isOnboardingComplete(status)) {
    return <Navigate to="/student/dashboard" replace />;
  }

  // If learning profile is complete but diagnostics are not, show diagnostics page
  if (status.learning_profile_complete) {
    return <Navigate to="/student/onboarding/profile" replace />;
  }

  // Otherwise, must complete questionnaire first
  return <Navigate to="/student/onboarding/profile" replace />;
}
