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
