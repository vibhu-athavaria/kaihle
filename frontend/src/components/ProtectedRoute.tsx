import React from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext";
import { getAuthHeader } from "@/lib/authToken";
import { UserRole } from "../types";

interface ProtectedRouteProps {
  children: React.ReactNode;
  role: UserRole | UserRole[];
  allowParentForProfile?: boolean;
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
  allowParentForProfile = false,
}) => {
  const { user, loading } = useAuth();
  const location = useLocation();

  const hasToken = !!getAuthHeader();
  const allowedRoles = Array.isArray(role) ? role : [role];

  // Special case: allow parents to access profile completion if they have a currentChild
  if (allowParentForProfile && user?.role === 'parent') {
    const currentChild = JSON.parse(localStorage.getItem('currentChild') || 'null');
    if (currentChild && currentChild.id) {
      allowedRoles.push('parent');
    }
  }

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
    // When allowParentForProfile is true, prioritize parent login for profile completion
    const redirectRole = allowParentForProfile && allowedRoles.includes('parent') ? 'parent' : allowedRoles[0];
    return (
      <Navigate
        to={LOGIN_ROUTE_BY_ROLE[redirectRole]}
        state={{ from: location }}
        replace
      />
    );
  }

  // Token exists but wrong role (important!)
  if (user && !allowedRoles.includes(user.role)) {
    return (
      <Navigate
        to={LOGIN_ROUTE_BY_ROLE[user.role]}
        replace
      />
    );
  }

  return <>{children}</>;
};
