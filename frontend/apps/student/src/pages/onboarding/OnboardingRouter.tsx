import { Navigate } from "react-router-dom";
import { useOnboardingStatus } from "../../hooks/useOnboardingStatus";

/**
 * OnboardingRouter - Gate 1 (Learning Profile) only.
 *
 * Gate 1 (global): Dashboard is inaccessible until the learning profile
 * questionnaire is complete. Once complete, the student sees their dashboard
 * with all class cards.
 *
 * Gate 2 (per-class): Each class card independently shows locked/unlocked state.
 * This is handled by ClassCard component, NOT by this router.
 *
 * The diagnostic status per class does NOT block access to the dashboard.
 * Students can always reach /student/dashboard once learning profile is complete.
 * They will see locked class cards for classes where diagnostic is not yet complete.
 */
export function OnboardingRouter() {
  const { data: status, isPending } = useOnboardingStatus();

  if (isPending || !status) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-primary" />
      </div>
    );
  }

  // Gate 1: Learning profile must be complete before dashboard is accessible
  if (!status.learning_profile_complete) {
    return <Navigate to="/student/onboarding/profile" replace />;
  }

  // Learning profile is complete - show dashboard
  // Gate 2 (per-class diagnostic lock) is handled by ClassCard component
  return <Navigate to="/student/dashboard" replace />;
}
