import React from "react";
import {
  render,
  screen,
  fireEvent,
  waitFor,
  within,
} from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AdminQuality } from "../pages/AdminQuality";
import { apiClient } from "@kaihle/auth";
import type { QualityRateRow, EvalSettings } from "../hooks/useAdminQuality";

const mockGet = apiClient.get as jest.Mock;
const mockPut = apiClient.put as jest.Mock;

function makeRate(overrides: Partial<QualityRateRow> = {}): QualityRateRow {
  return {
    week_start: null,
    task: "question_generation",
    check_name: "mcq_has_one_correct_answer",
    kind: "deterministic",
    rubric_status: null,
    is_indicative: false,
    passed: 36,
    failed: 4,
    indeterminate: 2,
    n: 40,
    pass_rate: 0.9,
    ci_low: 0.769,
    ci_high: 0.96,
    ...overrides,
  };
}

function makeSettings(overrides: Partial<EvalSettings> = {}): EvalSettings {
  return {
    eval_monthly_budget_usd: 10,
    eval_enabled_tasks: [],
    eval_sample_size_per_task: 50,
    eval_window_days: 7,
    eval_include_indicative: false,
    student_text_acknowledgements: {},
    available_tasks: ["question_generation", "grade_open_answer"],
    tasks_with_student_text: ["grade_open_answer"],
    updated_by: null,
    updated_at: null,
    ...overrides,
  };
}

interface Fixture {
  rates: QualityRateRow[];
  settings: EvalSettings;
  failures: {
    usage_event_id: string;
    check_name: string;
    task: string;
    created_at: string;
  }[];
}

function setupApi(f: Partial<Fixture> = {}) {
  const fx: Fixture = {
    rates: [makeRate()],
    settings: makeSettings(),
    failures: [],
    ...f,
  };
  mockGet.mockImplementation((url: string) => {
    if (url.endsWith("/quality/summary")) {
      return Promise.resolve({
        data: {
          window_start: "2026-09-19T00:00:00Z",
          window_end: "2026-10-17T00:00:00Z",
          bucket: "none",
          rates: fx.rates,
          truncated: false,
        },
      });
    }
    if (url.endsWith("/quality/failures")) {
      return Promise.resolve({
        data: {
          failures: fx.failures,
          total: fx.failures.length,
          page: 1,
          page_size: 20,
        },
      });
    }
    if (url.endsWith("/quality/budget")) {
      return Promise.resolve({
        data: {
          monthly_budget_usd: fx.settings.eval_monthly_budget_usd,
          month_to_date_spend_usd: 2.5,
          remaining_usd: 7.5,
        },
      });
    }
    if (url.endsWith("/eval-runs")) {
      return Promise.resolve({
        // One settled run: the shared EmptyState heading uses font-display, so the Inter check
        // below needs every table non-empty.
        data: {
          runs: [
            {
              id: "run-1",
              task: "question_generation",
              window_start: "2026-10-10T00:00:00Z",
              window_end: "2026-10-17T00:00:00Z",
              seed: "s",
              trigger: "manual",
              status: "completed",
              include_indicative: false,
              judge_model: null,
              sampled_count: 1,
              evaluated_count: 1,
              skipped_not_independent_count: 0,
              skipped_scrub_failed_count: 0,
              skipped_unsupported_count: 0,
              spend_usd: "0",
              error_type: null,
              requested_by: null,
              created_at: "2026-10-17T08:00:00Z",
              started_at: null,
              completed_at: null,
            },
          ],
          total: 1,
          page: 1,
          page_size: 10,
        },
      });
    }
    if (url.endsWith("/eval-settings")) {
      return Promise.resolve({ data: fx.settings });
    }
    if (url.includes("/llm-logs/")) {
      return Promise.resolve({
        data: {
          id: "evt-1",
          created_at: "2026-10-10T12:00:00Z",
          task: "question_generation",
          model: "test/model-a",
          component: null,
          run_id: null,
          prompt_tokens: 1,
          completion_tokens: 1,
          total_tokens: 2,
          latency_ms: 5,
          estimated_cost_usd: 0.001,
          succeeded: true,
          error_type: null,
          prompt_text: "PROMPT-BODY",
          response_text: "RESPONSE-BODY",
          error_detail: null,
          correlation_id: null,
          school_id: null,
          streamed: false,
        },
      });
    }
    return Promise.reject(new Error(`unexpected GET ${url}`));
  });
  mockPut.mockImplementation((_url: string, body: Record<string, unknown>) =>
    Promise.resolve({ data: { ...fx.settings, ...body } }),
  );
  return fx;
}

function renderPage() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <AdminQuality />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  mockGet.mockReset();
  mockPut.mockReset();
});

test("test_quality_page_when_summary_loading_then_renders_skeleton_not_spinner", () => {
  mockGet.mockReturnValue(new Promise(() => {}));
  const { container } = renderPage();
  expect(container.querySelector(".animate-pulse")).not.toBeNull();
  expect(container.querySelector('[role="status"]')).toBeNull();
});

test("test_quality_page_when_no_results_then_renders_explicit_empty_state", async () => {
  setupApi({ rates: [] });
  renderPage();
  expect(
    await screen.findByText(/no evaluation results yet/i),
  ).toBeInTheDocument();
});

test("test_quality_page_when_rates_present_then_shows_pass_rate_with_sample_size_and_interval", async () => {
  setupApi();
  renderPage();
  const row = (await screen.findByText("mcq_has_one_correct_answer")).closest(
    "tr",
  ) as HTMLElement;
  expect(within(row).getByText("90.0%")).toBeInTheDocument();
  expect(within(row).getByText(/n = 40/)).toBeInTheDocument();
  expect(within(row).getByText(/95% CI 76\.9%.96\.0%/)).toBeInTheDocument();
  expect(within(row).getByText(/2 indeterminate/i)).toBeInTheDocument();
});

test("test_quality_page_when_n_is_zero_then_shows_no_data_not_zero_percent", async () => {
  setupApi({
    rates: [
      makeRate({
        passed: 0,
        failed: 0,
        n: 0,
        indeterminate: 3,
        pass_rate: null,
        ci_low: null,
        ci_high: null,
      }),
    ],
  });
  renderPage();
  const row = (await screen.findByText("mcq_has_one_correct_answer")).closest(
    "tr",
  ) as HTMLElement;
  expect(within(row).getByText(/no measurable data/i)).toBeInTheDocument();
  expect(within(row).queryByText("0.0%")).toBeNull();
});

test("test_quality_page_when_rubric_indicative_then_labelled_indicative", async () => {
  setupApi({
    rates: [
      makeRate({
        check_name: "clear_stem",
        kind: "judge",
        rubric_status: "INDICATIVE",
        is_indicative: true,
      }),
    ],
  });
  renderPage();
  const row = (await screen.findByText("clear_stem")).closest(
    "tr",
  ) as HTMLElement;
  expect(within(row).getByText(/^indicative$/i)).toBeInTheDocument();
});

test("test_quality_page_when_budget_loaded_then_shows_budget_spend_and_remaining", async () => {
  setupApi();
  renderPage();
  const panel = await screen.findByRole("region", {
    name: /evaluation budget/i,
  });
  await waitFor(() => {
    expect(within(panel).getByText("$10.00")).toBeInTheDocument();
  });
  expect(within(panel).getByText("$2.50")).toBeInTheDocument();
  expect(within(panel).getByText("$7.50")).toBeInTheDocument();
});

test("test_quality_page_when_budget_saved_then_puts_full_settings_with_new_budget", async () => {
  setupApi();
  renderPage();
  const input = await screen.findByLabelText(/monthly budget \(usd\)/i);
  fireEvent.change(input, { target: { value: "25.5" } });
  fireEvent.click(screen.getByRole("button", { name: /save budget/i }));
  await waitFor(() => expect(mockPut).toHaveBeenCalledTimes(1));
  const [url, body] = mockPut.mock.calls[0];
  expect(url).toBe("/api/v1/platform/eval-settings");
  expect(body).toMatchObject({
    eval_monthly_budget_usd: 25.5,
    eval_enabled_tasks: [],
    eval_sample_size_per_task: 50,
    eval_window_days: 7,
    eval_include_indicative: false,
    acknowledge_student_text_tasks: [],
  });
});

test("test_quality_page_when_budget_negative_then_shows_error_and_does_not_save", async () => {
  setupApi();
  renderPage();
  const input = await screen.findByLabelText(/monthly budget \(usd\)/i);
  fireEvent.change(input, { target: { value: "-1" } });
  fireEvent.click(screen.getByRole("button", { name: /save budget/i }));
  expect(await screen.findByRole("alert")).toHaveTextContent(
    /cannot be negative/i,
  );
  expect(mockPut).not.toHaveBeenCalled();
});

test("test_quality_page_when_server_rejects_settings_then_shows_server_message", async () => {
  setupApi();
  mockPut.mockRejectedValue({
    response: { data: { detail: "budget too large" } },
  });
  renderPage();
  const input = await screen.findByLabelText(/monthly budget \(usd\)/i);
  fireEvent.change(input, { target: { value: "5" } });
  fireEvent.click(screen.getByRole("button", { name: /save budget/i }));
  expect(await screen.findByRole("alert")).toHaveTextContent(
    /budget too large/i,
  );
});

test("test_quality_page_when_student_text_task_enabled_then_requires_acknowledgement_in_modal", async () => {
  setupApi();
  renderPage();
  const toggle = await screen.findByRole("switch", {
    name: /enable grade_open_answer/i,
  });
  fireEvent.click(toggle);

  const dialog = await screen.findByRole("dialog");
  expect(mockPut).not.toHaveBeenCalled();
  const confirm = within(dialog).getByRole("button", { name: /enable task/i });
  expect(confirm).toBeDisabled();

  fireEvent.click(within(dialog).getByRole("checkbox"));
  expect(confirm).not.toBeDisabled();
  fireEvent.click(confirm);

  await waitFor(() => expect(mockPut).toHaveBeenCalledTimes(1));
  expect(mockPut.mock.calls[0][1]).toMatchObject({
    eval_enabled_tasks: ["grade_open_answer"],
    acknowledge_student_text_tasks: ["grade_open_answer"],
  });
});

test("test_quality_page_when_task_without_student_text_enabled_then_saves_without_modal", async () => {
  setupApi();
  renderPage();
  fireEvent.click(
    await screen.findByRole("switch", { name: /enable question_generation/i }),
  );
  await waitFor(() => expect(mockPut).toHaveBeenCalledTimes(1));
  expect(screen.queryByRole("dialog")).toBeNull();
  expect(mockPut.mock.calls[0][1]).toMatchObject({
    eval_enabled_tasks: ["question_generation"],
    acknowledge_student_text_tasks: [],
  });
});

test("test_quality_page_when_student_text_already_acknowledged_then_enables_without_modal", async () => {
  setupApi({
    settings: makeSettings({
      student_text_acknowledgements: {
        grade_open_answer: {
          acknowledged_by: "u1",
          acknowledged_at: "2026-10-01T00:00:00Z",
        },
      },
    }),
  });
  renderPage();
  fireEvent.click(
    await screen.findByRole("switch", { name: /enable grade_open_answer/i }),
  );
  await waitFor(() => expect(mockPut).toHaveBeenCalledTimes(1));
  expect(screen.queryByRole("dialog")).toBeNull();
});

test("test_quality_page_when_rendered_then_shows_best_effort_scrubbing_notice", async () => {
  setupApi();
  renderPage();
  expect(await screen.findByText(/best-effort scrubbing/i)).toBeInTheDocument();
});

test("test_quality_page_when_failure_row_clicked_then_opens_existing_llm_log_entry_by_event_id", async () => {
  setupApi({
    failures: [
      {
        usage_event_id: "evt-1",
        check_name: "mcq_has_one_correct_answer",
        task: "question_generation",
        created_at: "2026-10-10T12:00:00Z",
      },
    ],
  });
  renderPage();
  fireEvent.click(
    await screen.findByRole("button", { name: /open llm log evt-1/i }),
  );
  expect(await screen.findByText("PROMPT-BODY")).toBeInTheDocument();
  expect(
    mockGet.mock.calls.some((c) => c[0] === "/api/v1/platform/llm-logs/evt-1"),
  ).toBe(true);
});

test("test_quality_page_when_no_failures_then_shows_failures_empty_state", async () => {
  setupApi();
  renderPage();
  expect(await screen.findByText(/no failing checks/i)).toBeInTheDocument();
});

test("test_quality_page_when_rendered_then_uses_inter_typography_and_no_display_fonts", async () => {
  // Non-empty tables: the shared EmptyState heading uses font-display and is out of scope here.
  setupApi({
    failures: [
      {
        usage_event_id: "evt-1",
        check_name: "mcq_has_one_correct_answer",
        task: "question_generation",
        created_at: "2026-10-10T12:00:00Z",
      },
    ],
  });
  const { container } = renderPage();
  await screen.findAllByText("mcq_has_one_correct_answer");
  const main = container.querySelector("main") as HTMLElement;
  expect(main.innerHTML).toContain("font-['Inter']");
  expect(main.innerHTML).not.toMatch(
    /font-display|font-fraunces|font-\['Lora'\]/,
  );
});
