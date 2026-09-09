/**
 * @jest-environment jsdom
 */
import { renderHook, waitFor } from "@testing-library/react";
import { usePendingReviewCount } from "../usePendingReviewCount";

jest.mock("@kaihle/auth", () => ({
  apiClient: { get: jest.fn() },
}));

import { apiClient } from "@kaihle/auth";
const mockGet = apiClient.get as jest.Mock;

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";

function wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return React.createElement(QueryClientProvider, { client: qc }, children);
}

describe("usePendingReviewCount", () => {
  beforeEach(() => jest.clearAllMocks());

  it("test_usePendingReviewCount_when_pending_items_exist_then_returns_count", async () => {
    mockGet.mockResolvedValue({
      data: [{ subtopic_id: "a" }, { subtopic_id: "b" }],
    });
    const { result } = renderHook(() => usePendingReviewCount(), { wrapper });

    await waitFor(() => expect(result.current.data).toBe(2));
    expect(mockGet).toHaveBeenCalledWith(
      "/api/v1/teachers/me/explanation-review?status=pending",
    );
  });

  it("test_usePendingReviewCount_when_no_pending_items_then_returns_zero", async () => {
    mockGet.mockResolvedValue({ data: [] });
    const { result } = renderHook(() => usePendingReviewCount(), { wrapper });

    await waitFor(() => expect(result.current.data).toBe(0));
  });

  it("test_usePendingReviewCount_when_request_fails_then_returns_undefined_not_throws", async () => {
    mockGet.mockRejectedValue(new Error("network error"));
    const { result } = renderHook(() => usePendingReviewCount(), { wrapper });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.data).toBeUndefined();
  });
});
