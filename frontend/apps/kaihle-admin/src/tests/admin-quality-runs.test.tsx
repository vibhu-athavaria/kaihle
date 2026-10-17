import React from "react";
import {
  act,
  render,
  screen,
  fireEvent,
  waitFor,
  within,
} from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AdminQuality } from "../pages/AdminQuality";
import { apiClient } from "@kaihle/auth";
import {
  runsRefetchInterval,
  RUNS_POLL_INTERVAL_MS,
  type EvalRun,
  type EvalSettings,
} from "../hooks/useAdminQuality";

const mockGet = apiClient.get as jest.Mock;
const mockPost = apiClient.post as jest.Mock;
const RUNS_URL = "/api/v1/platform/eval-runs";

function makeSettings(overrides: Partial<EvalSettings> = {}): EvalSettings {
  return {
    eval_monthly_budget_usd: 10,
    eval_enabled_tasks: ["question_generation"],
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

function makeRun(overrides: Partial<EvalRun> = {}): EvalRun {
  return {
    id: "run-1",
    task: "question_generation",
    window_start: "2026-10-10T00:00:00Z",
    window_end: "2026-10-17T00:00:00Z",
    seed: "seed-1",
    trigger: "manual",
    status: "completed",
    include_indicative: false,
    judge_model: "test/judge",
    sampled_count: 50,
    evaluated_count: 40,
    skipped_not_independent_count: 4,
    skipped_scrub_failed_count: 3,
    skipped_unsupported_count: 3,
    spend_usd: "0.123400",
    error_type: null,
    requested_by: "user-1",
    created_at: "2026-10-17T08:00:00Z",
    started_at: "2026-10-17T08:00:05Z",
    completed_at: "2026-10-17T08:01:00Z",
    ...overrides,
  };
}

interface Fixture {
  settings: EvalSettings;
  runs: EvalRun[];
  total?: number;
}

function setupApi(f: Partial<Fixture> = {}) {
  const fx: Fixture = { settings: makeSettings(), runs: [], ...f };
  mockGet.mockImplementation((url: string) => {
    if (url.endsWith("/quality/summary")) {
      return Promise.resolve({
        data: {
          window_start: "2026-09-19T00:00:00Z",
          window_end: "2026-10-17T00:00:00Z",
          bucket: "none",
          rates: [],
          truncated: false,
        },
      });
    }
    if (url.endsWith("/quality/failures")) {
      return Promise.resolve({
        data: { failures: [], total: 0, page: 1, page_size: 20 },
      });
    }
    if (url.endsWith("/quality/budget")) {
      return Promise.resolve({
        data: {
          monthly_budget_usd: fx.settings.eval_monthly_budget_usd,
          month_to_date_spend_usd: 0,
          remaining_usd: fx.settings.eval_monthly_budget_usd,
        },
      });
    }
    if (url.endsWith("/eval-settings")) {
      return Promise.resolve({ data: fx.settings });
    }
    if (url === RUNS_URL) {
      return Promise.resolve({
        data: {
          runs: fx.runs,
          total: fx.total ?? fx.runs.length,
          page: 1,
          page_size: 10,
        },
      });
    }
    return Promise.reject(new Error(`unexpected GET ${url}`));
  });
  return fx;
}

function renderPage() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  const utils = render(
    <QueryClientProvider client={client}>
      <AdminQuality />
    </QueryClientProvider>,
  );
  return { ...utils, client };
}

async function findRunButton() {
  return screen.findByRole("button", { name: /run now/i });
}

function runsCalls() {
  return mockGet.mock.calls.filter((c) => c[0] === RUNS_URL).length;
}

beforeEach(() => {
  mockGet.mockReset();
  mockPost.mockReset();
});

test("test_run_controls_when_budget_is_zero_then_disables_run_now_with_visible_reason", async () => {
  setupApi({ settings: makeSettings({ eval_monthly_budget_usd: 0 }) });
  renderPage();
  const button = await findRunButton();
  expect(button).toBeDisabled();
  expect(
    screen.getByText(/monthly budget is 0.*set a budget above 0/i),
  ).toBeInTheDocument();
  fireEvent.click(button);
  expect(mockPost).not.toHaveBeenCalled();
});

test("test_run_controls_when_no_task_is_enabled_then_disables_run_now_with_visible_reason", async () => {
  setupApi({ settings: makeSettings({ eval_enabled_tasks: [] }) });
  renderPage();
  const button = await findRunButton();
  expect(button).toBeDisabled();
  expect(screen.getByText(/no task is enabled/i)).toBeInTheDocument();
});

test("test_run_controls_when_task_selected_then_lists_only_enabled_tasks", async () => {
  setupApi();
  renderPage();
  const select = await screen.findByLabelText(/task to run/i);
  const options = within(select).getAllByRole("option");
  expect(options.map((o) => o.textContent)).toEqual(["question_generation"]);
});

test("test_run_controls_when_double_clicked_then_sends_one_explicit_seed_and_window", async () => {
  setupApi();
  let resolve: (v: unknown) => void = () => {};
  mockPost.mockReturnValue(new Promise((r) => (resolve = r)));
  renderPage();
  const button = await findRunButton();
  fireEvent.click(button);
  fireEvent.click(button);

  await waitFor(() => expect(mockPost).toHaveBeenCalled());
  const bodies = mockPost.mock.calls.map((c) => c[1]);
  expect(mockPost.mock.calls[0][0]).toBe(RUNS_URL);
  expect(typeof bodies[0].seed).toBe("string");
  expect(bodies[0].seed.length).toBeGreaterThan(0);
  expect(bodies[0].window_start).toEqual(expect.any(String));
  expect(bodies[0].window_end).toEqual(expect.any(String));
  expect(bodies[0].task).toBe("question_generation");
  // Anything that did get through carries the identical seed and window.
  for (const body of bodies) expect(body).toEqual(bodies[0]);
  expect(button).toBeDisabled();

  await act(async () => {
    resolve({ status: 201, data: makeRun({ status: "pending" }) });
  });
});

test("test_run_controls_when_run_created_then_confirms_and_refreshes_runs_list", async () => {
  setupApi();
  mockPost.mockResolvedValue({ status: 201, data: makeRun() });
  renderPage();
  const before = runsCalls();
  fireEvent.click(await findRunButton());
  expect(await screen.findByRole("status")).toHaveTextContent(/run started/i);
  await waitFor(() => expect(runsCalls()).toBeGreaterThan(before));
});

test("test_run_controls_when_run_already_exists_then_says_so", async () => {
  setupApi();
  mockPost.mockResolvedValue({ status: 200, data: makeRun() });
  renderPage();
  fireEvent.click(await findRunButton());
  expect(await screen.findByRole("status")).toHaveTextContent(
    /already exists.*nothing new was started/i,
  );
});

test("test_run_controls_when_server_returns_422_then_shows_server_message", async () => {
  setupApi();
  mockPost.mockRejectedValue({
    response: {
      status: 422,
      data: { detail: "This task cannot be evaluated right now." },
    },
  });
  renderPage();
  fireEvent.click(await findRunButton());
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "This task cannot be evaluated right now.",
  );
  expect(
    screen.queryByRole("button", { name: /retry with a new seed/i }),
  ).toBeNull();
});

test("test_run_controls_when_server_returns_503_then_offers_retry_with_a_new_seed", async () => {
  setupApi();
  mockPost
    .mockRejectedValueOnce({
      response: { status: 503, data: { detail: "worker unavailable" } },
    })
    .mockResolvedValueOnce({ status: 201, data: makeRun() });
  renderPage();
  fireEvent.click(await findRunButton());
  expect(await screen.findByRole("alert")).toHaveTextContent(
    /worker is unavailable/i,
  );
  fireEvent.click(
    screen.getByRole("button", { name: /retry with a new seed/i }),
  );
  await waitFor(() => expect(mockPost).toHaveBeenCalledTimes(2));
  const first = mockPost.mock.calls[0][1];
  const second = mockPost.mock.calls[1][1];
  expect(second.seed).not.toBe(first.seed);
  expect(await screen.findByRole("status")).toHaveTextContent(/run started/i);
});

test("test_runs_list_when_runs_present_then_renders_skip_reasons_spend_and_status_text", async () => {
  setupApi({
    runs: [
      makeRun(),
      makeRun({
        id: "run-2",
        status: "failed",
        error_type: "JudgeUnusableError",
        trigger: "scheduled",
        evaluated_count: 0,
        skipped_not_independent_count: 0,
        skipped_scrub_failed_count: 0,
        skipped_unsupported_count: 0,
        spend_usd: "0",
      }),
    ],
  });
  renderPage();
  const region = await screen.findByRole("region", {
    name: /evaluation runs/i,
  });
  const done = (await within(region).findByText("$0.1234")).closest(
    "tr",
  ) as HTMLElement;
  expect(within(done).getByText(/^completed$/i)).toBeInTheDocument();
  expect(within(done).getByText(/40 of 50 evaluated/i)).toBeInTheDocument();
  expect(within(done).getByText(/4 not independent/i)).toBeInTheDocument();
  expect(within(done).getByText(/3 scrub failed/i)).toBeInTheDocument();
  expect(within(done).getByText(/3 unsupported/i)).toBeInTheDocument();
  expect(within(done).getByText(/manual/i)).toBeInTheDocument();

  const failed = within(region)
    .getByText(/^failed$/i)
    .closest("tr");
  expect(
    within(failed as HTMLElement).getByText(/JudgeUnusableError/),
  ).toBeInTheDocument();
  expect(
    within(failed as HTMLElement).getByText(/scheduled/i),
  ).toBeInTheDocument();
});

test("test_runs_list_when_no_runs_then_renders_explicit_empty_state", async () => {
  setupApi({ runs: [] });
  renderPage();
  expect(
    await screen.findByText(/no evaluation runs yet/i),
  ).toBeInTheDocument();
});

test("test_runs_list_when_loading_then_renders_skeleton_rows", () => {
  mockGet.mockReturnValue(new Promise(() => {}));
  renderPage();
  const region = screen.getByRole("region", { name: /evaluation runs/i });
  expect(region.querySelector(".animate-pulse")).not.toBeNull();
});

test("test_runs_list_when_more_than_one_page_then_shows_pager", async () => {
  setupApi({ runs: [makeRun()], total: 25 });
  renderPage();
  const region = await screen.findByRole("region", {
    name: /evaluation runs/i,
  });
  expect(await within(region).findByText(/page 1 of 3/i)).toBeInTheDocument();
  fireEvent.click(within(region).getByRole("button", { name: /next/i }));
  await waitFor(() =>
    expect(
      mockGet.mock.calls.some(
        (c) => c[0] === RUNS_URL && c[1]?.params?.page === 2,
      ),
    ).toBe(true),
  );
});

test("test_runs_refetch_interval_when_run_pending_or_running_then_polls_else_stops", () => {
  const page = (statuses: EvalRun["status"][]) => ({
    runs: statuses.map((status, i) => makeRun({ id: `r${i}`, status })),
    total: statuses.length,
    page: 1,
    page_size: 10,
  });
  expect(runsRefetchInterval(page(["pending"]))).toBe(RUNS_POLL_INTERVAL_MS);
  expect(runsRefetchInterval(page(["completed", "running"]))).toBe(
    RUNS_POLL_INTERVAL_MS,
  );
  expect(
    runsRefetchInterval(
      page(["completed", "failed", "empty", "budget_exhausted"]),
    ),
  ).toBe(false);
  expect(runsRefetchInterval(undefined)).toBe(false);
});

describe("polling", () => {
  beforeEach(() => jest.useFakeTimers({ advanceTimers: true }));
  afterEach(() => jest.useRealTimers());

  test("test_runs_list_when_run_active_then_polls_and_stops_after_it_settles_and_refreshes_quality", async () => {
    const fx = setupApi({ runs: [makeRun({ status: "running" })] });
    renderPage();
    await screen.findByText(/^running$/i);
    const afterLoad = runsCalls();
    const summaryBefore = mockGet.mock.calls.filter((c) =>
      c[0].endsWith("/quality/summary"),
    ).length;

    fx.runs = [makeRun({ status: "completed" })];
    await act(async () => {
      jest.advanceTimersByTime(RUNS_POLL_INTERVAL_MS + 100);
    });
    await screen.findByText(/^completed$/i);
    expect(runsCalls()).toBe(afterLoad + 1);
    await waitFor(() =>
      expect(
        mockGet.mock.calls.filter((c) => c[0].endsWith("/quality/summary"))
          .length,
      ).toBeGreaterThan(summaryBefore),
    );

    const settled = runsCalls();
    await act(async () => {
      jest.advanceTimersByTime(RUNS_POLL_INTERVAL_MS * 3);
    });
    expect(runsCalls()).toBe(settled);
  });

  test("test_runs_list_when_no_run_active_then_does_not_poll", async () => {
    setupApi({ runs: [makeRun({ status: "completed" })] });
    renderPage();
    await screen.findByText(/^completed$/i);
    const settled = runsCalls();
    await act(async () => {
      jest.advanceTimersByTime(RUNS_POLL_INTERVAL_MS * 3);
    });
    expect(runsCalls()).toBe(settled);
  });
});
