import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@kaihle/auth";

export type LlmUsageGroupBy = "task" | "component" | "model" | "run_id";

export interface LlmUsageBucket {
  bucket: string;
  calls: number;
  failures: number;
  tokens: number;
  cost: number | null;
  p50_ms: number;
  p95_ms: number;
}

export interface LlmUsageSummary {
  calls: number;
  tokens: number;
  cost: number | null;
  unpriced_count: number;
  unpriced_percent: number;
  unpriced_models: string[];
  unattributed_count: number;
  unattributed_percent: number;
  failures: number;
  p95_ms: number;
}

export interface LlmUsageResponse {
  since: string;
  group_by: LlmUsageGroupBy;
  buckets: LlmUsageBucket[];
  summary: LlmUsageSummary;
  unit_costs: [string, string][];
  page: number;
  page_size: number;
  total_buckets: number;
}

export function useAdminLlmUsage(params: {
  since?: string;
  groupBy: LlmUsageGroupBy;
  page?: number;
  pageSize?: number;
  /** The recent-runs table only reads `buckets`/`total_buckets` — skip the unit-cost
   * queries on that call so the backend doesn't compute a result nothing renders. */
  includeUnitCosts?: boolean;
}) {
  const {
    since,
    groupBy,
    page = 1,
    pageSize = 20,
    includeUnitCosts = true,
  } = params;

  return useQuery({
    queryKey: [
      "admin",
      "llm-usage",
      { since, groupBy, page, pageSize, includeUnitCosts },
    ],
    queryFn: async () => {
      const response = await apiClient.get("/api/v1/platform/llm-usage", {
        params: {
          since,
          group_by: groupBy,
          page,
          page_size: pageSize,
          include_unit_costs: includeUnitCosts,
        },
      });
      return response.data as LlmUsageResponse;
    },
  });
}
