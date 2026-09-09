import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@kaihle/auth";

export type LlmLogSortBy =
  | "created_at"
  | "task"
  | "model"
  | "latency_ms"
  | "cost"
  | "tokens";
export type LlmLogSortDir = "asc" | "desc";

export interface LlmLogSummary {
  id: string;
  created_at: string;
  task: string;
  model: string;
  component: string | null;
  run_id: string | null;
  prompt_tokens: number | null;
  completion_tokens: number | null;
  total_tokens: number | null;
  latency_ms: number;
  estimated_cost_usd: number | null;
  succeeded: boolean;
  error_type: string | null;
}

export interface LlmLogsResponse {
  logs: LlmLogSummary[];
  total: number;
  page: number;
  page_size: number;
}

export interface LlmLogDetail extends LlmLogSummary {
  prompt_text: string | null;
  response_text: string | null;
  error_detail: string | null;
  correlation_id: string | null;
  school_id: string | null;
  streamed: boolean;
}

export interface LlmLogFilterOptions {
  tasks: string[];
  models: string[];
}

export function useAdminLlmLogs(params: {
  page?: number;
  pageSize?: number;
  task?: string;
  model?: string;
  sortBy?: LlmLogSortBy;
  sortDir?: LlmLogSortDir;
}) {
  const {
    page = 1,
    pageSize = 50,
    task,
    model,
    sortBy = "created_at",
    sortDir = "desc",
  } = params;

  return useQuery({
    queryKey: [
      "admin",
      "llm-logs",
      { page, pageSize, task, model, sortBy, sortDir },
    ],
    queryFn: async () => {
      const response = await apiClient.get("/api/v1/platform/llm-logs", {
        params: {
          page,
          page_size: pageSize,
          task,
          model,
          sort_by: sortBy,
          sort_dir: sortDir,
        },
      });
      return response.data as LlmLogsResponse;
    },
  });
}

/** The full set of task/model values that actually have logged calls — for the filter
 * dropdowns. Fetched once per page mount, not on every list refetch. */
export function useAdminLlmLogFilterOptions() {
  return useQuery({
    queryKey: ["admin", "llm-logs", "filter-options"],
    queryFn: async () => {
      const response = await apiClient.get(
        "/api/v1/platform/llm-logs/filter-options",
      );
      return response.data as LlmLogFilterOptions;
    },
  });
}

/** Fetched only when a row is clicked (`enabled`) — the list view never carries
 * prompt/response text, so the detail is its own targeted request. */
export function useAdminLlmLogDetail(logId: string | null) {
  return useQuery({
    queryKey: ["admin", "llm-logs", "detail", logId],
    queryFn: async () => {
      const response = await apiClient.get(
        `/api/v1/platform/llm-logs/${logId}`,
      );
      return response.data as LlmLogDetail;
    },
    enabled: !!logId,
  });
}
