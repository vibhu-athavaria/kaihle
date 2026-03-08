import React, { useEffect, useState } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useAuthStore } from "./tokenStore";
import { apiClient } from "./apiClient";

/**
 * PrivateRoute — redirects unauthenticated users to /login
 */
export function PrivateRoute({ children }: { children: React.ReactNode }) {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const location = useLocation();

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }
  return <>{children}</>;
}

/**
 * RoleRoute — redirects users whose role is not in allowedRoles to /unauthorised
 */
export function RoleRoute({
  children,
  allowedRoles,
}: {
  children: React.ReactNode;
  allowedRoles: string[];
}) {
  const user = useAuthStore((s) => s.user);

  if (!user || !allowedRoles.includes(user.role)) {
    return <Navigate to="/unauthorised" replace />;
  }
  return <>{children}</>;
}

type OnboardingStatus = {
  learning_profile_complete: boolean;
  diagnostics_complete: boolean;
  overall: "PENDING" | "IN_PROGRESS" | "COMPLETED";
};

/**
 * OnboardingRoute — for STUDENT role only.
 * Redirects to /student/onboarding if onboarding is not complete.
 *
 * Uses the /api/v1/onboarding/status endpoint to determine completion.
 * Shows a loading spinner while checking.
 *
 * Only applies to STUDENT role. Other roles pass through immediately.
 */
export function OnboardingRoute({ children }: { children: React.ReactNode }) {
  const user = useAuthStore((s) => s.user);
  const [status, setStatus] = useState<OnboardingStatus | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!user || user.role !== "STUDENT") {
      setLoading(false);
      return;
    }
    apiClient
      .get<OnboardingStatus>("/api/v1/onboarding/status")
      .then((res) => setStatus(res.data))
      .catch(() => setStatus(null))
      .finally(() => setLoading(false));
  }, [user]);

  if (!user) return <Navigate to="/login" replace />;
  if (user.role !== "STUDENT") return <>{children}</>;
  if (loading)
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-teal-600" />
      </div>
    );
  if (!status || status.overall !== "COMPLETED") {
    return <Navigate to="/student/onboarding" replace />;
  }
  return <>{children}</>;
}
