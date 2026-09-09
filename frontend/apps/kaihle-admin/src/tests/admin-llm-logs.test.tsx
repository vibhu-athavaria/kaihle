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

test("test_llm_logs_page_when_filter_options_loaded_then_dropdowns_populated", async () => {
  mockGet.mockImplementation((url: string) => {
    if (url.includes("filter-options")) {
      return Promise.resolve({
        data: {
          tasks: ["lesson_plan", "question_generation"],
          models: ["test/model-a"],
        },
      });
    }
    return Promise.resolve({
      data: { logs: [makeSummary()], total: 1, page: 1, page_size: 50 },
    });
  });

  renderPage();

  const taskSelect = await screen.findByLabelText(/^task$/i);
  await waitFor(() => {
    expect(
      Array.from(taskSelect.querySelectorAll("option")).map(
        (o) => o.textContent,
      ),
    ).toEqual(["All tasks", "lesson_plan", "question_generation"]);
  });

  const modelSelect = screen.getByLabelText(/^model$/i);
  await waitFor(() => {
    expect(
      Array.from(modelSelect.querySelectorAll("option")).map(
        (o) => o.textContent,
      ),
    ).toEqual(["All models", "test/model-a"]);
  });
});

test("test_llm_logs_page_when_task_filter_selected_then_list_refetches_with_task_param", async () => {
  mockGet.mockImplementation((url: string) => {
    if (url.includes("filter-options")) {
      return Promise.resolve({
        data: {
          tasks: ["lesson_plan", "question_generation"],
          models: ["test/model-a"],
        },
      });
    }
    return Promise.resolve({
      data: { logs: [makeSummary()], total: 1, page: 1, page_size: 50 },
    });
  });

  renderPage();

  await screen.findByText("$1.23");
  const taskSelect = await screen.findByLabelText(/^task$/i);
  await waitFor(() => {
    expect(
      taskSelect.querySelector('option[value="lesson_plan"]'),
    ).not.toBeNull();
  });
  mockGet.mockClear();

  fireEvent.change(taskSelect, { target: { value: "lesson_plan" } });

  await waitFor(() => {
    const listCall = mockGet.mock.calls.find(
      (call) => call[0] === "/api/v1/platform/llm-logs",
    );
    expect(listCall?.[1]?.params?.task).toBe("lesson_plan");
  });
});

test("test_llm_logs_page_when_column_header_clicked_then_sort_params_sent", async () => {
  mockGet.mockResolvedValue({
    data: { logs: [makeSummary()], total: 1, page: 1, page_size: 50 },
  });

  renderPage();

  await screen.findByText("question_generation");
  mockGet.mockClear();

  fireEvent.click(screen.getByRole("button", { name: /sort by latency/i }));

  await waitFor(() => {
    const listCall = mockGet.mock.calls.find(
      (call) => call[0] === "/api/v1/platform/llm-logs",
    );
    expect(listCall?.[1]?.params?.sort_by).toBe("latency_ms");
    expect(listCall?.[1]?.params?.sort_dir).toBe("desc");
  });
});

test("test_llm_logs_page_when_same_column_clicked_twice_then_sort_direction_toggles", async () => {
  mockGet.mockResolvedValue({
    data: { logs: [makeSummary()], total: 1, page: 1, page_size: 50 },
  });

  renderPage();

  await screen.findByText("question_generation");

  const latencyHeader = screen.getByRole("button", {
    name: /sort by latency/i,
  });
  fireEvent.click(latencyHeader);
  await waitFor(() => {
    const listCall = mockGet.mock.calls
      .filter((call) => call[0] === "/api/v1/platform/llm-logs")
      .at(-1);
    expect(listCall?.[1]?.params?.sort_dir).toBe("desc");
  });

  fireEvent.click(latencyHeader);
  await waitFor(() => {
    const listCall = mockGet.mock.calls
      .filter((call) => call[0] === "/api/v1/platform/llm-logs")
      .at(-1);
    expect(listCall?.[1]?.params?.sort_dir).toBe("asc");
  });
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
