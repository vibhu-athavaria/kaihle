import { jsx as _jsx } from "react/jsx-runtime";
import { Navigate } from "react-router-dom";
import { useOnboardingStatus } from "../../hooks/useOnboardingStatus";
export function OnboardingRouter() {
    const { status, isLoading } = useOnboardingStatus();
    if (isLoading || !status) {
        return (_jsx("div", { className: "flex items-center justify-center h-screen", children: _jsx("div", { className: "animate-spin rounded-full h-8 w-8 border-b-2 border-brand-primary" }) }));
    }
    // If learning profile is complete, go to dashboard
    if (status.learning_profile_complete) {
        return _jsx(Navigate, { to: "/student/dashboard", replace: true });
    }
    // Otherwise, must complete questionnaire first
    return _jsx(Navigate, { to: "/student/onboarding/profile", replace: true });
}
