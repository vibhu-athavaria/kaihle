import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AdminLlmLogs } from "../pages/AdminLlmLogs";
import { apiClient } from "@kaihle/auth";
import type { LlmLogSummary, LlmLogDetail } from "../hooks/useAdminLlmLogs";

const mockGet = apiClient.get as jest.Mock;

function makeSummary(overrides: Partial<LlmLogSummary> = {}): LlmLogSummary {
  return {
    id: "log-1",
    created_at: "2026-09-09T12:00:00Z",
    task: "question_generation",
    model: "test/model-a",
    component: "script:generate_gap_questions",
    run_id: "run-1",
    prompt_tokens: 100,
    completion_tokens: 200,
    total_tokens: 300,
    latency_ms: 500,
    estimated_cost_usd: 1.23,
    succeeded: true,
    error_type: null,
    ...overrides,
  };
}

function makeDetail(overrides: Partial<LlmLogDetail> = {}): LlmLogDetail {
  return {
    ...makeSummary(),
    prompt_text: "[user] What is 2+2?",
    response_text: "4",
    error_detail: null,
    correlation_id: "corr-1",
    school_id: null,
    streamed: false,
    ...overrides,
  };
}

function renderPage() {
  const client = new QueryClient();
  return render(
    <QueryClientProvider client={client}>
      <AdminLlmLogs />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  mockGet.mockReset();
});

test("test_llm_logs_page_when_loading_then_renders_skeleton_not_spinner", () => {
  mockGet.mockReturnValue(new Promise(() => {}));

  const { container } = renderPage();

  expect(container.querySelector(".animate-pulse")).not.toBeNull();
  expect(container.querySelector('[role="status"]')).toBeNull();
});

test("test_llm_logs_page_when_no_data_then_renders_empty_state", async () => {
  mockGet.mockResolvedValue({
    data: { logs: [], total: 0, page: 1, page_size: 50 },
  });

  renderPage();

  expect(await screen.findByText(/no llm calls recorded/i)).toBeInTheDocument();
});

test("test_llm_logs_page_when_data_present_then_table_rows_rendered", async () => {
  mockGet.mockResolvedValue({
    data: { logs: [makeSummary()], total: 1, page: 1, page_size: 50 },
  });

  renderPage();

  expect(await screen.findByText("question_generation")).toBeInTheDocument();
  expect(screen.getByText("test/model-a")).toBeInTheDocument();
});

test("test_llm_logs_page_when_sub_cent_cost_then_not_rounded_to_zero", async () => {
  mockGet.mockResolvedValue({
    data: {
      logs: [makeSummary({ estimated_cost_usd: 0.0005 })],
      total: 1,
      page: 1,
      page_size: 50,
    },
  });

  renderPage();

  await screen.findByText("question_generation");
  expect(screen.queryByText("$0.00")).toBeNull();
  expect(screen.getByText("$0.000500")).toBeInTheDocument();
});

test("test_llm_logs_page_when_call_failed_then_error_badge_shown", async () => {
  mockGet.mockResolvedValue({
    data: {
      logs: [makeSummary({ succeeded: false, error_type: "RateLimitError" })],
      total: 1,
      page: 1,
      page_size: 50,
    },
  });

  renderPage();

  expect(await screen.findByText("RateLimitError")).toBeInTheDocument();
});

test("test_llm_logs_page_when_row_clicked_then_detail_modal_fetches_and_shows_prompt_and_response", async () => {
  mockGet.mockImplementation((url: string) => {
    if (url.includes("/llm-logs/log-1")) {
      return Promise.resolve({ data: makeDetail() });
    }
    return Promise.resolve({
      data: { logs: [makeSummary()], total: 1, page: 1, page_size: 50 },
    });
  });

  renderPage();

  const row = await screen.findByText("question_generation");
  fireEvent.click(row.closest("tr") as HTMLElement);

  await waitFor(() => {
    expect(screen.getByText("[user] What is 2+2?")).toBeInTheDocument();
  });
  expect(screen.getByText("4")).toBeInTheDocument();
});

test("test_llm_logs_page_when_first_page_then_previous_button_disabled", async () => {
  mockGet.mockResolvedValue({
    data: {
      logs: Array.from({ length: 50 }, (_, i) =>
        makeSummary({ id: `log-${i}` }),
      ),
      total: 120,
      page: 1,
      page_size: 50,
    },
  });

  renderPage();

  await screen.findByText(/page 1 of/i);
  expect(screen.getByText(/previous/i).closest("button")).toBeDisabled();
  expect(screen.getByText(/next/i).closest("button")).not.toBeDisabled();
});
