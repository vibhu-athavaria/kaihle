/**
 * @jest-environment jsdom
 */
import { act, renderHook, waitFor } from "@testing-library/react";
import { useCourseStatus } from "../useCourseStatus";

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

describe("useCourseStatus", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  it("test_useCourseStatus_when_status_generating_then_polls_again_after_5s", async () => {
    mockGet.mockResolvedValue({
      data: {
        status: "generating",
        subtopic_count: 4,
        gaps_count: 0,
        video_coverage: { covered: 0, total: 4 },
      },
    });
    renderHook(() => useCourseStatus("topic-1"), { wrapper });

    await waitFor(() => expect(mockGet).toHaveBeenCalledTimes(1));

    await act(async () => {
      jest.advanceTimersByTime(5_000);
    });
    await waitFor(() => expect(mockGet).toHaveBeenCalledTimes(2));
  });

  it("test_useCourseStatus_when_status_partial_then_does_not_poll_forever", async () => {
    mockGet.mockResolvedValue({
      data: {
        status: "partial",
        subtopic_count: 4,
        gaps_count: 2,
        video_coverage: { covered: 4, total: 4 },
      },
    });
    renderHook(() => useCourseStatus("topic-1"), { wrapper });

    await waitFor(() => expect(mockGet).toHaveBeenCalledTimes(1));

    // "partial" is a settled state, same as "ready"/"failed" — the hook's
    // refetchInterval only returns 5000 for "generating". A regression that treated
    // "partial" like "generating" would show a second call here.
    await act(async () => {
      jest.advanceTimersByTime(10_000);
    });
    expect(mockGet).toHaveBeenCalledTimes(1);
  });

  it("test_useCourseStatus_when_status_ready_then_returns_gaps_count_zero", async () => {
    mockGet.mockResolvedValue({
      data: {
        status: "ready",
        subtopic_count: 4,
        gaps_count: 0,
        video_coverage: { covered: 4, total: 4 },
      },
    });
    const { result } = renderHook(() => useCourseStatus("topic-1"), {
      wrapper,
    });

    await waitFor(() => expect(result.current.data?.status).toBe("ready"));
    expect(result.current.data?.gaps_count).toBe(0);
  });
});
