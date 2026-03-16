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

  // If learning profile is complete, go to dashboard
  if (status.learning_profile_complete) {
    return <Navigate to="/student/dashboard" replace />;
  }

  // Otherwise, must complete questionnaire first
  return <Navigate to="/student/onboarding/profile" replace />;
}
