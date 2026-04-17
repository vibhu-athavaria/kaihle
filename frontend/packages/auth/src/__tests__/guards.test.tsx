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

  test("test_onboarding_route_when_learning_profile_incomplete_then_redirects_to_onboarding", async () => {
    // Arrange: profile NOT complete
    useAuthStore
      .getState()
      .setTokens("access", "refresh", mockUser({ role: "STUDENT" }));
    (apiClient.get as jest.Mock).mockResolvedValue({
      data: {
        learning_profile_complete: false,
        diagnostics_by_class: [],
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
    expect(screen.queryByText("Dashboard Content")).not.toBeInTheDocument();
  });

  test("test_onboarding_route_when_learning_profile_complete_then_passes_through", async () => {
    // Arrange: profile complete (Gate 1 satisfied — diagnostics irrelevant to this gate)
    useAuthStore
      .getState()
      .setTokens("access", "refresh", mockUser({ role: "STUDENT" }));
    (apiClient.get as jest.Mock).mockResolvedValue({
      data: {
        learning_profile_complete: true,
        diagnostics_by_class: [],
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

  test("test_onboarding_route_when_profile_complete_and_diagnostics_pending_then_still_passes_through", async () => {
    // ST-008: students with Maths (COMPLETED) + Science (PENDING) must NOT be blocked
    useAuthStore
      .getState()
      .setTokens("access", "refresh", mockUser({ role: "STUDENT" }));
    (apiClient.get as jest.Mock).mockResolvedValue({
      data: {
        learning_profile_complete: true,
        diagnostics_by_class: [
          {
            class_id: "cls-maths",
            class_name: "Maths 9A",
            status: "COMPLETED",
          },
          { class_id: "cls-sci", class_name: "Science 9A", status: "PENDING" },
        ],
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

    // Profile is complete → student MUST reach dashboard even with PENDING diagnostics
    await waitFor(() => {
      expect(screen.getByText("Dashboard Content")).toBeInTheDocument();
    });
    expect(screen.queryByText("Onboarding Page")).not.toBeInTheDocument();
  });

  test("test_onboarding_route_when_teacher_role_then_passes_through_without_api_call", async () => {
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

    // Non-STUDENT roles skip the check entirely
    expect(screen.getByText("Dashboard Content")).toBeInTheDocument();
    expect(apiClient.get).not.toHaveBeenCalled();
  });
});
