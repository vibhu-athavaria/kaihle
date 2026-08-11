import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { ImpersonateRoute } from "../ImpersonateRoute";
import { useAuthStore } from "../tokenStore";

// Mocked with a factory so the real apiClient module is never loaded. It reads
// import.meta.env, which cannot be compiled under this package's CommonJS jest
// transform.
const mockPost = jest.fn();
jest.mock("../apiClient", () => ({
  apiClient: { post: (...args: unknown[]) => mockPost(...args) },
}));

const REDEEM_URL = "/api/v1/auth/impersonate/redeem";

const redeemResponse = {
  data: {
    access_token: "impersonated-access-token",
    refresh_token: null,
    token_type: "bearer",
    must_change_password: false,
    user: {
      id: "student-1",
      email: "sam@example.com",
      username: "sam",
      first_name: "Sam",
      role: "STUDENT",
      school_id: "school-1",
      permissions: null,
    },
    impersonator: { id: "admin-1", name: "Ada Admin" },
  },
};

function renderAt(url: string) {
  return render(
    <MemoryRouter initialEntries={[url]}>
      <Routes>
        <Route
          path="/impersonate"
          element={<ImpersonateRoute homePath="/student/dashboard" />}
        />
        <Route
          path="/student/dashboard"
          element={<div>Student dashboard</div>}
        />
      </Routes>
    </MemoryRouter>,
  );
}

describe("ImpersonateRoute", () => {
  beforeEach(() => {
    mockPost.mockReset();
    useAuthStore.getState().clearTokens();
  });

  test("stores the impersonated session and redirects home on success", async () => {
    mockPost.mockResolvedValue(redeemResponse);

    renderAt("/impersonate?token=good-token");

    expect(await screen.findByText("Student dashboard")).toBeInTheDocument();
    expect(mockPost).toHaveBeenCalledWith(REDEEM_URL, { token: "good-token" });

    const state = useAuthStore.getState();
    expect(state.accessToken).toBe("impersonated-access-token");
    expect(state.isAuthenticated).toBe(true);
    expect(state.impersonator).toEqual({ id: "admin-1", name: "Ada Admin" });
  });

  test("stores no refresh token, so the session cannot shed its marker", async () => {
    // A refresh would rebuild the access token from the user row and drop the
    // `act` claim, turning an impersonated session into an unmarked one.
    mockPost.mockResolvedValue(redeemResponse);

    renderAt("/impersonate?token=good-token");

    await screen.findByText("Student dashboard");
    expect(useAuthStore.getState().refreshToken).toBeNull();
  });

  test("redeems the token exactly once", async () => {
    // The token is single-use; a double POST would burn it and fail the second.
    mockPost.mockResolvedValue(redeemResponse);

    renderAt("/impersonate?token=good-token");

    await screen.findByText("Student dashboard");
    expect(mockPost).toHaveBeenCalledTimes(1);
  });

  test("shows an error and authenticates nobody when the token is rejected", async () => {
    mockPost.mockRejectedValue(new Error("401"));

    renderAt("/impersonate?token=stale-token");

    expect(await screen.findByText(/no longer valid/i)).toBeInTheDocument();
    expect(useAuthStore.getState().isAuthenticated).toBe(false);
  });

  test("shows an error without calling the API when the token is missing", async () => {
    renderAt("/impersonate");

    expect(await screen.findByText(/missing its token/i)).toBeInTheDocument();
    await waitFor(() => expect(mockPost).not.toHaveBeenCalled());
  });
});
