import { useEffect, useRef } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@kaihle/auth";

const BASE = "/api/v1/platform";

export type QualityBucket = "week" | "none";

export interface QualityRateRow {
  week_start: string | null;
  task: string;
  check_name: string;
  kind: "deterministic" | "judge";
  rubric_status: string | null;
  is_indicative: boolean;
  passed: number;
  failed: number;
  indeterminate: number;
  // passed + failed. Indeterminate results are NOT part of n.
  n: number;
  // null when n === 0 ("nothing measured", not "0% passed").
  pass_rate: number | null;
  ci_low: number | null;
  ci_high: number | null;
}

export interface QualitySummary {
  window_start: string;
  window_end: string;
  bucket: QualityBucket;
  rates: QualityRateRow[];
  truncated: boolean;
}

export interface QualityFailure {
  usage_event_id: string;
  check_name: string;
  task: string;
  created_at: string;
}

export interface QualityFailuresPage {
  failures: QualityFailure[];
  total: number;
  page: number;
  page_size: number;
}

export interface QualityBudget {
  monthly_budget_usd: number;
  month_to_date_spend_usd: number;
  remaining_usd: number;
}

export interface StudentTextAcknowledgement {
  acknowledged_by: string;
  acknowledged_at: string;
}

export interface EvalSettings {
  eval_monthly_budget_usd: number;
  eval_enabled_tasks: string[];
  eval_sample_size_per_task: number;
  eval_window_days: number;
  eval_include_indicative: boolean;
  student_text_acknowledgements: Record<string, StudentTextAcknowledgement>;
  available_tasks: string[];
  tasks_with_student_text: string[];
  updated_by: string | null;
  updated_at: string | null;
}

/** PUT /eval-settings is a full replacement, so every save carries the whole editable set. */
export interface EvalSettingsUpdate {
  eval_monthly_budget_usd: number;
  eval_enabled_tasks: string[];
  eval_sample_size_per_task: number;
  eval_window_days: number;
  eval_include_indicative: boolean;
  acknowledge_student_text_tasks: string[];
}

export function buildSettingsUpdate(
  current: EvalSettings,
  changes: Partial<EvalSettingsUpdate> = {},
): EvalSettingsUpdate {
  return {
    eval_monthly_budget_usd: current.eval_monthly_budget_usd,
    eval_enabled_tasks: current.eval_enabled_tasks,
    eval_sample_size_per_task: current.eval_sample_size_per_task,
    eval_window_days: current.eval_window_days,
    eval_include_indicative: current.eval_include_indicative,
    acknowledge_student_text_tasks: [],
    ...changes,
  };
}

export function useQualitySummary(params: {
  task?: string;
  bucket: QualityBucket;
}) {
  const { task, bucket } = params;
  return useQuery({
    queryKey: ["admin", "quality", "summary", { task, bucket }],
    queryFn: async () => {
      const response = await apiClient.get(`${BASE}/quality/summary`, {
        params: { task, bucket },
      });
      return response.data as QualitySummary;
    },
  });
}

export function useQualityFailures(params: {
  task?: string;
  page: number;
  pageSize: number;
}) {
  const { task, page, pageSize } = params;
  return useQuery({
    queryKey: ["admin", "quality", "failures", { task, page, pageSize }],
    queryFn: async () => {
      // page_size is sent explicitly: the backend default (50) differs from the page size the
      // pager below assumes, which would otherwise make the page count wrong.
      const response = await apiClient.get(`${BASE}/quality/failures`, {
        params: { task, page, page_size: pageSize },
      });
      return response.data as QualityFailuresPage;
    },
  });
}

export function useQualityBudget() {
  return useQuery({
    queryKey: ["admin", "quality", "budget"],
    queryFn: async () => {
      const response = await apiClient.get(`${BASE}/quality/budget`);
      return response.data as QualityBudget;
    },
  });
}

export function useEvalSettings() {
  return useQuery({
    queryKey: ["admin", "quality", "settings"],
    queryFn: async () => {
      const response = await apiClient.get(`${BASE}/eval-settings`);
      return response.data as EvalSettings;
    },
  });
}

/** Saves settings, then refreshes the settings and the budget readout (the budget panel
 * reads the saved value back from the server rather than trusting the form). */
export function useSaveEvalSettings() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: EvalSettingsUpdate) => {
      const response = await apiClient.put(`${BASE}/eval-settings`, body);
      return response.data as EvalSettings;
    },
    onSuccess: (saved) => {
      queryClient.setQueryData(["admin", "quality", "settings"], saved);
      queryClient.invalidateQueries({
        queryKey: ["admin", "quality", "budget"],
      });
    },
  });
}

/** The backend returns 422 with a human-readable `detail` for every rule violation. */
export function settingsErrorMessage(error: unknown): string {
  const detail = (error as { response?: { data?: { detail?: unknown } } })
    ?.response?.data?.detail;
  return typeof detail === "string" && detail
    ? detail
    : "Could not save settings. Please try again.";
}

export type EvalRunStatus =
  | "pending"
  | "running"
  | "completed"
  | "failed"
  | "budget_exhausted"
  | "empty";

/** Metadata, counts and spend only. The API never returns any prompt or response text. */
export interface EvalRun {
  id: string;
  task: string;
  window_start: string;
  window_end: string;
  seed: string;
  trigger: "manual" | "scheduled";
  status: EvalRunStatus;
  include_indicative: boolean;
  judge_model: string | null;
  sampled_count: number;
  evaluated_count: number;
  skipped_not_independent_count: number;
  skipped_scrub_failed_count: number;
  skipped_unsupported_count: number;
  // Decimal serialised as a string, e.g. "0.123400".
  spend_usd: string;
  error_type: string | null;
  requested_by: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
}

export interface EvalRunsPage {
  runs: EvalRun[];
  total: number;
  page: number;
  page_size: number;
}

export interface EvalRunCreateRequest {
  task: string;
  window_start: string;
  window_end: string;
  seed: string;
}

export interface EvalRunCreateResult {
  run: EvalRun;
  // 201 = newly enqueued; 200 = an identical (task, window, seed) run already existed.
  created: boolean;
}

export const RUNS_POLL_INTERVAL_MS = 5000;

const RUNS_QUERY_KEY = ["admin", "quality", "runs"] as const;

export function isRunActive(run: Pick<EvalRun, "status">): boolean {
  return run.status === "pending" || run.status === "running";
}

/** Poll only while a listed run is still pending or running; false stops polling. */
export function runsRefetchInterval(
  data: EvalRunsPage | undefined,
): number | false {
  return data?.runs.some(isRunActive) ? RUNS_POLL_INTERVAL_MS : false;
}

/** Recent runs, newest first. Refreshes the quality read models when a run leaves
 * pending/running, because that is when new results (and spend) become visible. */
export function useEvalRuns(params: { page: number; pageSize: number }) {
  const { page, pageSize } = params;
  const queryClient = useQueryClient();
  const query = useQuery({
    queryKey: [...RUNS_QUERY_KEY, { page, pageSize }],
    queryFn: async () => {
      const response = await apiClient.get(`${BASE}/eval-runs`, {
        params: { page, page_size: pageSize },
      });
      return response.data as EvalRunsPage;
    },
    refetchInterval: (q) => runsRefetchInterval(q.state.data),
  });

  const activeIds = useRef<Set<string>>(new Set());
  const runs = query.data?.runs;
  useEffect(() => {
    if (!runs) return;
    const settled = runs.some(
      (r) => activeIds.current.has(r.id) && !isRunActive(r),
    );
    activeIds.current = new Set(runs.filter(isRunActive).map((r) => r.id));
    if (settled) {
      for (const part of ["summary", "failures", "budget"]) {
        queryClient.invalidateQueries({ queryKey: ["admin", "quality", part] });
      }
    }
  }, [runs, queryClient]);

  return query;
}

/** Enqueues a run. The caller supplies the seed and window so a repeat submit of the same
 * intent is idempotent server-side. */
export function useCreateEvalRun() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (
      body: EvalRunCreateRequest,
    ): Promise<EvalRunCreateResult> => {
      const response = await apiClient.post(`${BASE}/eval-runs`, body);
      return {
        run: response.data as EvalRun,
        created: response.status === 201,
      };
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: RUNS_QUERY_KEY });
    },
  });
}

/** One click-intent: generated once and reused until the request settles. */
export function newRunIntent(
  task: string,
  windowDays: number,
  now: Date = new Date(),
): EvalRunCreateRequest {
  const end = new Date(now);
  const start = new Date(end.getTime() - windowDays * 24 * 60 * 60 * 1000);
  const seed = `${now.getTime().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
  return {
    task,
    window_start: start.toISOString(),
    window_end: end.toISOString(),
    seed,
  };
}

export function httpStatusOf(error: unknown): number | undefined {
  return (error as { response?: { status?: number } })?.response?.status;
}

/** The server's human-readable `detail` (422), or the supplied fallback. */
export function runErrorDetail(error: unknown, fallback: string): string {
  const detail = (error as { response?: { data?: { detail?: unknown } } })
    ?.response?.data?.detail;
  return typeof detail === "string" && detail ? detail : fallback;
}
