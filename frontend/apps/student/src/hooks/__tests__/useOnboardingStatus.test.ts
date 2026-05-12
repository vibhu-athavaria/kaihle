/**
 * @jest-environment jsdom
 *
 * Tests for useOnboardingStatus hook (ST-003).
 *
 * Verifies that the hook uses React Query's loading state machinery,
 * not a manual useRef flag — so loading state cannot get permanently stuck.
 */

import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import { useOnboardingStatus } from "../useOnboardingStatus";
import { apiClient, useAuth } from "@kaihle/auth";

const mockedUseAuth = useAuth as jest.Mock;
const mockedApiGet = apiClient.get as jest.Mock;

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  const Component = ({ children }: { children: React.ReactNode }) =>
    React.createElement(QueryClientProvider, { client: queryClient }, children);
  Component.displayName = "QueryClientProvider";
  return Component;
}

beforeEach(() => {
  jest.clearAllMocks();
  mockedUseAuth.mockReturnValue({
    user: { id: "test-student-id", role: "STUDENT" },
    logout: jest.fn(),
  });
});

describe("useOnboardingStatus", () => {
  test("test_onboarding_status_when_user_exists_then_fetches_status_endpoint", async () => {
    // Arrange
    mockedApiGet.mockResolvedValueOnce({
      data: {
        learning_profile_complete: true,
      },
    });

    // Act
    const { result } = renderHook(() => useOnboardingStatus(), {
      wrapper: createWrapper(),
    });

    // Assert: eventually returns data
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.learning_profile_complete).toBe(true);
    expect(mockedApiGet).toHaveBeenCalledWith(
      "/api/v1/onboarding/status/test-student-id",
    );
  });

  test("test_onboarding_status_when_user_is_null_then_query_is_disabled", () => {
    // Arrange: no logged-in user
    mockedUseAuth.mockReturnValue({ user: null, logout: jest.fn() });

    // Act
    const { result } = renderHook(() => useOnboardingStatus(), {
      wrapper: createWrapper(),
    });

    // Assert: query is disabled — no fetch, data is undefined
    expect(result.current.fetchStatus).toBe("idle");
    expect(result.current.data).toBeUndefined();
    expect(mockedApiGet).not.toHaveBeenCalled();
  });

  test("test_onboarding_status_when_fetch_fails_then_isError_is_true", async () => {
    // Arrange
    mockedApiGet.mockRejectedValueOnce(new Error("Network error"));

    // Act
    const { result } = renderHook(() => useOnboardingStatus(), {
      wrapper: createWrapper(),
    });

    // Assert: isError reflects the failure (not permanently stuck on isPending)
    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.isPending).toBe(false);
  });

  test("test_onboarding_status_when_returns_data_then_isPending_is_false", async () => {
    // Arrange
    mockedApiGet.mockResolvedValueOnce({
      data: {
        learning_profile_complete: false,
      },
    });

    // Act
    const { result } = renderHook(() => useOnboardingStatus(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    // Assert: isPending false once data is available
    expect(result.current.isPending).toBe(false);
    expect(result.current.data?.learning_profile_complete).toBe(false);
  });
});
