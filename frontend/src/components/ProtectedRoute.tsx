import React from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext";
import { getAuthHeader } from "@/lib/authToken";
import { UserRole } from "../types";

interface ProtectedRouteProps {
  children: React.ReactNode;
  role: UserRole;
}

const LOGIN_ROUTE_BY_ROLE: Record<UserRole, string> = {
  parent: "/parent-login",
  student: "/student-login",
  admin: "/admin-login",
  teacher: "/teacher-login",
};

export const ProtectedRoute: React.FC<ProtectedRouteProps> = ({
  children,
  role,
}) => {
  const { user, loading } = useAuth();
  const location = useLocation();

  const hasToken = !!getAuthHeader();

  // Still restoring session
  if (loading) {
    return (
      <div className="min-h-screen bg-blue-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600">Loading your dashboard...</p>
        </div>
      </div>
    );
  }

  // No token → send to correct login
  if (!hasToken) {
    return (
      <Navigate
        to={LOGIN_ROUTE_BY_ROLE[role]}
        state={{ from: location }}
        replace
      />
    );
  }

  // Token exists but wrong role (important!)
  if (user && user.role !== role) {
    return (
      <Navigate
        to={LOGIN_ROUTE_BY_ROLE[user.role]}
        replace
      />
    );
  }

  return <>{children}</>;
};
