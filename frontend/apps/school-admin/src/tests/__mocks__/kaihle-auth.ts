/**
 * Jest mock for @kaihle/auth.
 * Provides a minimal apiClient stub for unit tests.
 */
export const apiClient = {
  get: jest.fn(),
  post: jest.fn(),
  put: jest.fn(),
  patch: jest.fn(),
  delete: jest.fn(),
};

export const useAuth = jest.fn(() => ({
  user: { id: "user-1", email: "admin@test.com", school_id: "school-1" },
  logout: jest.fn(),
}));

export const useAuthStore = jest.fn((selector) =>
  selector({
    user: { id: "user-1", email: "admin@test.com", school_id: "school-1" },
    accessToken: "test-token",
  }),
);

export const PrivateRoute = ({ children }: { children: React.ReactNode }) =>
  children;
export const PasswordSetupRoute = ({
  children,
}: {
  children: React.ReactNode;
}) => children;
export const RoleRoute = ({ children }: { children: React.ReactNode }) =>
  children;

import React from "react";
