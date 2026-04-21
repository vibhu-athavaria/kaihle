/**
 * @jest-environment jsdom
 */
import { renderHook, waitFor } from "@testing-library/react";
import { useStudentAssessments } from "../useStudentAssessments";

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

const TEACHER_ASSESSMENT = {
  id: "assess-1",
  class_id: "cls-1",
  title: "Chapter 3 Quiz",
  assessment_type: "PROGRESS_CHECK",
  is_system_generated: false,
  status: "ACTIVE",
  question_count: 10,
  deadline: null,
  published_at: "2026-04-01T00:00:00Z",
};

const DIAGNOSTIC_ASSESSMENT = {
  id: "assess-2",
  class_id: "cls-1",
  title: "Onboarding Diagnostic",
  assessment_type: "DIAGNOSTIC",
  is_system_generated: true,
  status: "ACTIVE",
  question_count: 20,
  deadline: null,
  published_at: "2026-04-01T00:00:00Z",
};

describe("useStudentAssessments", () => {
  beforeEach(() => jest.clearAllMocks());

  it("test_useStudentAssessments_when_empty_classIds_then_returns_empty_results", () => {
    mockGet.mockResolvedValue({ data: { data: [] } });
    const { result } = renderHook(
      () => useStudentAssessments([], "student-1"),
      { wrapper },
    );
    expect(result.current.diagnostics).toEqual([]);
    expect(result.current.teacherAssessments).toEqual([]);
    expect(result.current.newCount).toBe(0);
  });

  it("test_useStudentAssessments_when_has_teacher_assessment_then_separates_from_diagnostics", async () => {
    mockGet.mockImplementation((url: string) => {
      if (url.includes("/classes/")) {
        return Promise.resolve({
          data: { data: [TEACHER_ASSESSMENT, DIAGNOSTIC_ASSESSMENT] },
        });
      }
      return Promise.resolve({ data: { data: [] } });
    });

    const { result } = renderHook(
      () => useStudentAssessments(["cls-1"], "student-1"),
      { wrapper },
    );

    await waitFor(() => expect(result.current.isPending).toBe(false));

    expect(result.current.teacherAssessments).toHaveLength(1);
    expect(result.current.teacherAssessments[0].id).toBe("assess-1");
    expect(result.current.diagnostics).toHaveLength(1);
    expect(result.current.diagnostics[0].id).toBe("assess-2");
  });

  it("test_useStudentAssessments_when_active_teacher_assessment_not_attempted_then_newCount_is_1", async () => {
    mockGet.mockImplementation((url: string) => {
      if (url.includes("/classes/")) {
        return Promise.resolve({ data: { data: [TEACHER_ASSESSMENT] } });
      }
      return Promise.resolve({ data: { data: [] } });
    });

    const { result } = renderHook(
      () => useStudentAssessments(["cls-1"], "student-1"),
      { wrapper },
    );

    await waitFor(() => expect(result.current.isPending).toBe(false));
    expect(result.current.newCount).toBe(1);
  });

  it("test_useStudentAssessments_when_attempt_submitted_then_newCount_is_0", async () => {
    mockGet.mockImplementation((url: string) => {
      if (url.includes("/classes/")) {
        return Promise.resolve({ data: { data: [TEACHER_ASSESSMENT] } });
      }
      return Promise.resolve({
        data: {
          data: [
            {
              attempt_id: "att-1",
              assessment_id: "assess-1",
              status: "SUBMITTED",
              score: 0.8,
            },
          ],
        },
      });
    });

    const { result } = renderHook(
      () => useStudentAssessments(["cls-1"], "student-1"),
      { wrapper },
    );

    await waitFor(() => expect(result.current.isPending).toBe(false));
    expect(result.current.newCount).toBe(0);
    expect(result.current.teacherAssessments[0].attemptStatus).toBe(
      "COMPLETED",
    );
  });

  it("test_useStudentAssessments_when_attempt_in_progress_then_attemptStatus_is_IN_PROGRESS", async () => {
    mockGet.mockImplementation((url: string) => {
      if (url.includes("/classes/")) {
        return Promise.resolve({ data: { data: [TEACHER_ASSESSMENT] } });
      }
      return Promise.resolve({
        data: {
          data: [
            {
              attempt_id: "att-1",
              assessment_id: "assess-1",
              status: "IN_PROGRESS",
              score: null,
            },
          ],
        },
      });
    });

    const { result } = renderHook(
      () => useStudentAssessments(["cls-1"], "student-1"),
      { wrapper },
    );

    await waitFor(() => expect(result.current.isPending).toBe(false));
    expect(result.current.teacherAssessments[0].attemptStatus).toBe(
      "IN_PROGRESS",
    );
    expect(result.current.newCount).toBe(0);
  });
});
