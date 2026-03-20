import React from "react";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { PasswordSetupRoute } from "../PasswordSetupRoute";
import { useAuthStore, User } from "../tokenStore";

// Mock jwt-decode module - use require in beforeEach for proper hoisting
let mockDecode: jest.Mock;

jest.mock("jwt-decode", () => ({
  jwtDecode: (token: string) => mockDecode(token),
}));

const mockUser = (overrides?: Partial<User>): User => ({
  id: "user-123",
  email: "test@example.com",
  role: "TEACHER",
  school_id: "school-456",
  ...overrides,
});

describe("PasswordSetupRoute", () => {
  beforeEach(() => {
    useAuthStore.getState().clearTokens();
    mockDecode = jest.fn();
  });

  test("PasswordSetupRoute redirects to /teacher/setup-password when token has password_setup scope and user is TEACHER", () => {
    mockDecode.mockReturnValue({ scope: "password_setup" });
    useAuthStore
      .getState()
      .setTokens("scoped-token", "refresh", mockUser({ role: "TEACHER" }));

    render(
      <MemoryRouter initialEntries={["/teacher/dashboard"]}>
        <Routes>
          <Route
            path="/teacher/setup-password"
            element={<div>Setup Password Page</div>}
          />
          <Route
            path="/teacher/dashboard"
            element={
              <PasswordSetupRoute>
                <div>Dashboard Content</div>
              </PasswordSetupRoute>
            }
          />
        </Routes>
      </MemoryRouter>,
    );

    expect(screen.getByText("Setup Password Page")).toBeInTheDocument();
    expect(screen.queryByText("Dashboard Content")).not.toBeInTheDocument();
  });

  test("PasswordSetupRoute redirects to /school-admin/setup-password when token has password_setup scope and user is SCHOOL_ADMIN", () => {
    mockDecode.mockReturnValue({ scope: "password_setup" });
    useAuthStore
      .getState()
      .setTokens("scoped-token", "refresh", mockUser({ role: "SCHOOL_ADMIN" }));

    render(
      <MemoryRouter initialEntries={["/school-admin/dashboard"]}>
        <Routes>
          <Route
            path="/school-admin/setup-password"
            element={<div>Setup Password Page</div>}
          />
          <Route
            path="/school-admin/dashboard"
            element={
              <PasswordSetupRoute>
                <div>Dashboard Content</div>
              </PasswordSetupRoute>
            }
          />
        </Routes>
      </MemoryRouter>,
    );

    expect(screen.getByText("Setup Password Page")).toBeInTheDocument();
    expect(screen.queryByText("Dashboard Content")).not.toBeInTheDocument();
  });

  test("PasswordSetupRoute redirects to /kaihle-admin/setup-password when token has password_setup scope and user is KAIHLE_ADMIN", () => {
    mockDecode.mockReturnValue({ scope: "password_setup" });
    useAuthStore
      .getState()
      .setTokens("scoped-token", "refresh", mockUser({ role: "KAIHLE_ADMIN" }));

    render(
      <MemoryRouter initialEntries={["/kaihle-admin/dashboard"]}>
        <Routes>
          <Route
            path="/kaihle-admin/setup-password"
            element={<div>Setup Password Page</div>}
          />
          <Route
            path="/kaihle-admin/dashboard"
            element={
              <PasswordSetupRoute>
                <div>Dashboard Content</div>
              </PasswordSetupRoute>
            }
          />
        </Routes>
      </MemoryRouter>,
    );

    expect(screen.getByText("Setup Password Page")).toBeInTheDocument();
    expect(screen.queryByText("Dashboard Content")).not.toBeInTheDocument();
  });

  test("PasswordSetupRoute renders children when token has no password_setup scope", () => {
    mockDecode.mockReturnValue({});
    useAuthStore.getState().setTokens("full-token", "refresh", mockUser());

    render(
      <MemoryRouter initialEntries={["/teacher/dashboard"]}>
        <Routes>
          <Route
            path="/teacher/setup-password"
            element={<div>Setup Password Page</div>}
          />
          <Route
            path="/teacher/dashboard"
            element={
              <PasswordSetupRoute>
                <div>Dashboard Content</div>
              </PasswordSetupRoute>
            }
          />
        </Routes>
      </MemoryRouter>,
    );

    expect(screen.getByText("Dashboard Content")).toBeInTheDocument();
    expect(screen.queryByText("Setup Password Page")).not.toBeInTheDocument();
  });

  test("PasswordSetupRoute renders children when no token exists", () => {
    render(
      <MemoryRouter initialEntries={["/teacher/dashboard"]}>
        <Routes>
          <Route
            path="/teacher/setup-password"
            element={<div>Setup Password Page</div>}
          />
          <Route
            path="/teacher/dashboard"
            element={
              <PasswordSetupRoute>
                <div>Dashboard Content</div>
              </PasswordSetupRoute>
            }
          />
        </Routes>
      </MemoryRouter>,
    );

    expect(screen.getByText("Dashboard Content")).toBeInTheDocument();
    expect(screen.queryByText("Setup Password Page")).not.toBeInTheDocument();
  });

  test("PasswordSetupRoute renders children when user has no role", () => {
    mockDecode.mockReturnValue({ scope: "password_setup" });
    const userWithoutRole = {
      ...mockUser(),
      role: undefined,
    } as unknown as User;
    useAuthStore
      .getState()
      .setTokens("scoped-token", "refresh", userWithoutRole);

    render(
      <MemoryRouter initialEntries={["/teacher/dashboard"]}>
        <Routes>
          <Route
            path="/teacher/setup-password"
            element={<div>Setup Password Page</div>}
          />
          <Route
            path="/teacher/dashboard"
            element={
              <PasswordSetupRoute>
                <div>Dashboard Content</div>
              </PasswordSetupRoute>
            }
          />
        </Routes>
      </MemoryRouter>,
    );

    expect(screen.getByText("Dashboard Content")).toBeInTheDocument();
    expect(screen.queryByText("Setup Password Page")).not.toBeInTheDocument();
  });
});
