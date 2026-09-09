import React from "react";
import { render, screen, fireEvent, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AdminLlmUsage } from "../pages/AdminLlmUsage";
import * as hooks from "../hooks/useAdminLlmUsage";
import type {
  LlmUsageResponse,
  LlmUsageSummary,
} from "../hooks/useAdminLlmUsage";

jest.mock("../hooks/useAdminLlmUsage", () => ({
  ...jest.requireActual("../hooks/useAdminLlmUsage"),
  useAdminLlmUsage: jest.fn(),
}));

const mockUseAdminLlmUsage = hooks.useAdminLlmUsage as jest.Mock;

const ZERO_SUMMARY: LlmUsageSummary = {
  calls: 0,
  tokens: 0,
  cost: null,
  unpriced_count: 0,
  unpriced_percent: 0,
  unpriced_models: [],
  unattributed_count: 0,
  unattributed_percent: 0,
  failures: 0,
  p95_ms: 0,
};

function makeResponse(
  overrides: Partial<LlmUsageResponse> = {},
): LlmUsageResponse {
  return {
    since: "2026-08-01",
    group_by: "component",
    buckets: [],
    summary: ZERO_SUMMARY,
    unit_costs: [],
    page: 1,
    page_size: 20,
    total_buckets: 0,
    ...overrides,
  };
}

/** Both the main grouping call and the dedicated run_id call resolve to `mainResponse`
 * unless `runsResponse` is given — most tests don't care about the runs table. */
function mockHook(
  mainResponse: LlmUsageResponse | undefined,
  options: { isLoading?: boolean; runsResponse?: LlmUsageResponse } = {},
) {
  mockUseAdminLlmUsage.mockImplementation((params: { groupBy: string }) => {
    const isRuns = params.groupBy === "run_id";
    const data = isRuns
      ? (options.runsResponse ?? makeResponse({ group_by: "run_id" }))
      : mainResponse;
    return { data, isLoading: options.isLoading ?? false };
  });
}

function renderPage() {
  const client = new QueryClient();
  return render(
    <QueryClientProvider client={client}>
      <AdminLlmUsage />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  mockUseAdminLlmUsage.mockReset();
});

test("test_llm_usage_page_when_loading_then_renders_skeleton_not_spinner", () => {
  mockHook(undefined, { isLoading: true });

  const { container } = renderPage();

  expect(container.querySelector(".animate-pulse")).not.toBeNull();
  expect(container.querySelector('[role="status"]')).toBeNull();
  expect(screen.queryByLabelText(/spinner|loading/i)).toBeNull();
});

test("test_llm_usage_page_when_no_data_then_renders_empty_state", () => {
  mockHook(makeResponse({ buckets: [] }));

  renderPage();

  expect(
    screen.getByText(/no usage recorded in this window/i),
  ).toBeInTheDocument();
});

test("test_llm_usage_page_when_unpriced_zero_then_kpi_card_still_rendered", () => {
  mockHook(
    makeResponse({
      summary: { ...ZERO_SUMMARY, calls: 10, unpriced_percent: 0 },
    }),
  );

  renderPage();

  const label = screen.getByText("Unpriced");
  const card = label.closest("div.bg-white") as HTMLElement;
  expect(within(card).getByText("0.0%")).toBeInTheDocument();
});

test("test_llm_usage_page_when_unpriced_nonzero_then_warning_tint_applied", () => {
  mockHook(
    makeResponse({
      summary: {
        ...ZERO_SUMMARY,
        calls: 10,
        unpriced_count: 3,
        unpriced_percent: 30,
      },
    }),
  );

  renderPage();

  const value = screen.getByText("30.0%");
  expect(value.className).toMatch(/text-amber-600/);
});

test("test_llm_usage_page_when_unattributed_nonzero_then_warning_tint_applied", () => {
  mockHook(
    makeResponse({
      summary: {
        ...ZERO_SUMMARY,
        calls: 10,
        unattributed_count: 5,
        unattributed_percent: 50,
      },
    }),
  );

  renderPage();

  const value = screen.getByText("50.0%");
  expect(value.className).toMatch(/text-amber-600/);
});

test("test_llm_usage_page_when_data_present_then_bucket_table_rendered", () => {
  mockHook(
    makeResponse({
      buckets: [
        {
          bucket: "api:diagnostic",
          calls: 42,
          failures: 1,
          tokens: 1000,
          cost: 1.23,
          p50_ms: 200,
          p95_ms: 800,
        },
      ],
    }),
  );

  renderPage();

  expect(screen.getByText("api:diagnostic")).toBeInTheDocument();
  expect(screen.getByText("42")).toBeInTheDocument();
});

test("test_llm_usage_page_when_group_by_changed_then_hook_refetches_with_new_param", () => {
  mockHook(makeResponse());

  renderPage();

  const select = screen.getByLabelText(/group by/i);
  fireEvent.change(select, { target: { value: "model" } });

  expect(mockUseAdminLlmUsage).toHaveBeenCalledWith(
    expect.objectContaining({ groupBy: "model" }),
  );
});

test("test_llm_usage_page_when_sub_cent_cost_then_not_rounded_to_zero", () => {
  mockHook(
    makeResponse({
      buckets: [
        {
          bucket: "script:generate_gap_questions",
          calls: 5,
          failures: 0,
          tokens: 500,
          cost: 0.0005,
          p50_ms: 100,
          p95_ms: 300,
        },
      ],
    }),
  );

  renderPage();

  expect(screen.queryByText("$0.00")).toBeNull();
  expect(screen.getByText("$0.000500")).toBeInTheDocument();
});
