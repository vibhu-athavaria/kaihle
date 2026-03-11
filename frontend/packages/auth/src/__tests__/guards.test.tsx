import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { PrivateRoute, RoleRoute, OnboardingRoute } from "../guards";
import { useAuthStore, User } from "../tokenStore";
import { apiClient } from "../apiClient";

// Mock the apiClient
jest.mock("../apiClient", () => ({
  apiClient: {
    get: jest.fn(),
  },
}));

const mockUser = (overrides?: Partial<User>): User => ({
  id: "user-123",
  email: "test@example.com",
  role: "STUDENT",
  school_id: "school-456",
  ...overrides,
});

describe("PrivateRoute", () => {
  beforeEach(() => {
    useAuthStore.getState().clearTokens();
  });

  test("PrivateRoute redirects unauthenticated user to /login", () => {
    render(
      <MemoryRouter initialEntries={["/protected"]}>
        <Routes>
          <Route path="/login" element={<div>Login Page</div>} />
          <Route
            path="/protected"
            element={
              <PrivateRoute>
                <div>Protected Content</div>
              </PrivateRoute>
            }
          />
        </Routes>
      </MemoryRouter>,
    );

    expect(screen.getByText("Login Page")).toBeInTheDocument();
    expect(screen.queryByText("Protected Content")).not.toBeInTheDocument();
  });

  test("PrivateRoute renders children when authenticated", () => {
    useAuthStore.getState().setTokens("access", "refresh", mockUser());

    render(
      <MemoryRouter initialEntries={["/protected"]}>
        <Routes>
          <Route path="/login" element={<div>Login Page</div>} />
          <Route
            path="/protected"
            element={
              <PrivateRoute>
                <div>Protected Content</div>
              </PrivateRoute>
            }
          />
        </Routes>
      </MemoryRouter>,
    );

    expect(screen.getByText("Protected Content")).toBeInTheDocument();
    expect(screen.queryByText("Login Page")).not.toBeInTheDocument();
  });
});

describe("RoleRoute", () => {
  beforeEach(() => {
    useAuthStore.getState().clearTokens();
  });

  test("RoleRoute redirects when role not in allowedRoles", () => {
    useAuthStore
      .getState()
      .setTokens("access", "refresh", mockUser({ role: "STUDENT" }));

    render(
      <MemoryRouter initialEntries={["/admin"]}>
        <Routes>
          <Route path="/unauthorised" element={<div>Unauthorised</div>} />
          <Route
            path="/admin"
            element={
              <RoleRoute allowedRoles={["TEACHER", "SCHOOL_ADMIN"]}>
                <div>Admin Content</div>
              </RoleRoute>
            }
          />
        </Routes>
      </MemoryRouter>,
    );

    expect(screen.getByText("Unauthorised")).toBeInTheDocument();
    expect(screen.queryByText("Admin Content")).not.toBeInTheDocument();
  });

  test("RoleRoute renders children when role is in allowedRoles", () => {
    useAuthStore
      .getState()
      .setTokens("access", "refresh", mockUser({ role: "TEACHER" }));

    render(
      <MemoryRouter initialEntries={["/admin"]}>
        <Routes>
          <Route path="/unauthorised" element={<div>Unauthorised</div>} />
          <Route
            path="/admin"
            element={
              <RoleRoute allowedRoles={["TEACHER", "SCHOOL_ADMIN"]}>
                <div>Admin Content</div>
              </RoleRoute>
            }
          />
        </Routes>
      </MemoryRouter>,
    );

    expect(screen.getByText("Admin Content")).toBeInTheDocument();
    expect(screen.queryByText("Unauthorised")).not.toBeInTheDocument();
  });
});

describe("OnboardingRoute", () => {
  beforeEach(() => {
    useAuthStore.getState().clearTokens();
    jest.clearAllMocks();
  });

  test("OnboardingRoute redirects STUDENT with incomplete onboarding to /student/onboarding", async () => {
    useAuthStore
      .getState()
      .setTokens("access", "refresh", mockUser({ role: "STUDENT" }));
    (apiClient.get as jest.Mock).mockResolvedValue({
      data: {
        learning_profile_complete: true,
        diagnostics_complete: false,
        overall: "IN_PROGRESS",
      },
    });

    render(
      <MemoryRouter initialEntries={["/dashboard"]}>
        <Routes>
          <Route path="/login" element={<div>Login Page</div>} />
          <Route
            path="/student/onboarding"
            element={<div>Onboarding Page</div>}
          />
          <Route
            path="/dashboard"
            element={
              <OnboardingRoute>
                <div>Dashboard Content</div>
              </OnboardingRoute>
            }
          />
        </Routes>
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByText("Onboarding Page")).toBeInTheDocument();
    });
  });

  test("OnboardingRoute passes STUDENT with COMPLETED onboarding through", async () => {
    useAuthStore
      .getState()
      .setTokens("access", "refresh", mockUser({ role: "STUDENT" }));
    (apiClient.get as jest.Mock).mockResolvedValue({
      data: {
        learning_profile_complete: true,
        diagnostics_complete: true,
        overall: "COMPLETED",
      },
    });

    render(
      <MemoryRouter initialEntries={["/dashboard"]}>
        <Routes>
          <Route path="/login" element={<div>Login Page</div>} />
          <Route
            path="/student/onboarding"
            element={<div>Onboarding Page</div>}
          />
          <Route
            path="/dashboard"
            element={
              <OnboardingRoute>
                <div>Dashboard Content</div>
              </OnboardingRoute>
            }
          />
        </Routes>
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByText("Dashboard Content")).toBeInTheDocument();
    });
    expect(screen.queryByText("Onboarding Page")).not.toBeInTheDocument();
  });

  test("OnboardingRoute passes TEACHER through without checking onboarding status", async () => {
    useAuthStore
      .getState()
      .setTokens("access", "refresh", mockUser({ role: "TEACHER" }));

    render(
      <MemoryRouter initialEntries={["/dashboard"]}>
        <Routes>
          <Route path="/login" element={<div>Login Page</div>} />
          <Route
            path="/student/onboarding"
            element={<div>Onboarding Page</div>}
          />
          <Route
            path="/dashboard"
            element={
              <OnboardingRoute>
                <div>Dashboard Content</div>
              </OnboardingRoute>
            }
          />
        </Routes>
      </MemoryRouter>,
    );

    // Should render immediately without API call
    expect(screen.getByText("Dashboard Content")).toBeInTheDocument();
    expect(apiClient.get).not.toHaveBeenCalled();
  });
});
