import { Skeleton, EmptyState } from "@kaihle/ui";
import { LlmUsageBucket, LlmUsageGroupBy } from "../../hooks/useAdminLlmUsage";

interface UsageBucketTableProps {
  buckets: LlmUsageBucket[];
  loading: boolean;
  groupBy: LlmUsageGroupBy;
  onGroupByChange: (groupBy: LlmUsageGroupBy) => void;
}

const GROUP_BY_OPTIONS: { value: LlmUsageGroupBy; label: string }[] = [
  { value: "component", label: "Component" },
  { value: "task", label: "Task" },
  { value: "model", label: "Model" },
  { value: "run_id", label: "Run" },
];

/** Mirrors `format_cost()` in `app/services/llm_usage_service.py` — a raw per-call cost
 * is routinely $0.001-$0.00001, and rounding to 2dp would print $0.00 for every row. */
function formatCost(cost: number | null): string {
  if (cost === null) return "—";
  if (cost === 0) return "$0.00";
  if (Math.abs(cost) < 0.01) return `$${cost.toFixed(6)}`;
  if (Math.abs(cost) < 1) return `$${cost.toFixed(4)}`;
  return `$${cost.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

export function UsageBucketTable({
  buckets,
  loading,
  groupBy,
  onGroupByChange,
}: UsageBucketTableProps) {
  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <label
          htmlFor="usage-group-by"
          className="font-['Inter'] text-xs uppercase tracking-wide text-gray-400"
        >
          Group by
        </label>
        <select
          id="usage-group-by"
          value={groupBy}
          onChange={(e) => onGroupByChange(e.target.value as LlmUsageGroupBy)}
          className="font-['Inter'] text-sm border border-gray-200 rounded-lg px-3 py-1.5 text-gray-700 focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2"
        >
          {GROUP_BY_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </div>

      <div className="bg-white rounded-2xl border border-gray-200 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="bg-gray-50 border-b border-gray-200">
                <th className="text-left py-3 px-4 font-['Inter'] text-xs uppercase tracking-wide text-gray-400">
                  {GROUP_BY_OPTIONS.find((o) => o.value === groupBy)?.label}
                </th>
                <th className="text-right py-3 px-4 font-['Inter'] text-xs uppercase tracking-wide text-gray-400">
                  Calls
                </th>
                <th className="text-right py-3 px-4 font-['Inter'] text-xs uppercase tracking-wide text-gray-400">
                  Failures
                </th>
                <th className="text-right py-3 px-4 font-['Inter'] text-xs uppercase tracking-wide text-gray-400">
                  Tokens
                </th>
                <th className="text-right py-3 px-4 font-['Inter'] text-xs uppercase tracking-wide text-gray-400">
                  Cost
                </th>
                <th className="text-right py-3 px-4 font-['Inter'] text-xs uppercase tracking-wide text-gray-400">
                  p50
                </th>
                <th className="text-right py-3 px-4 font-['Inter'] text-xs uppercase tracking-wide text-gray-400">
                  p95
                </th>
              </tr>
            </thead>
            <tbody>
              {loading &&
                [...Array(5)].map((_, i) => (
                  <tr key={i} className="border-b border-gray-50">
                    {[...Array(7)].map((__, j) => (
                      <td key={j} className="py-4 px-4">
                        <Skeleton className="h-4 w-16" />
                      </td>
                    ))}
                  </tr>
                ))}
              {!loading &&
                buckets.map((bucket) => (
                  <tr
                    key={bucket.bucket}
                    className="border-b border-gray-50 hover:bg-gray-50 transition-colors duration-75"
                  >
                    <td className="py-4 px-4">
                      <span className="font-['Inter'] text-sm font-medium text-gray-700">
                        {bucket.bucket}
                      </span>
                    </td>
                    <td className="py-4 px-4 text-right">
                      <span className="font-['Inter'] text-sm text-gray-700">
                        {bucket.calls.toLocaleString()}
                      </span>
                    </td>
                    <td className="py-4 px-4 text-right">
                      <span
                        className={`font-['Inter'] text-sm ${bucket.failures > 0 ? "text-red-600" : "text-gray-400"}`}
                      >
                        {bucket.failures.toLocaleString()}
                      </span>
                    </td>
                    <td className="py-4 px-4 text-right">
                      <span className="font-['Inter'] text-sm text-gray-700">
                        {bucket.tokens.toLocaleString()}
                      </span>
                    </td>
                    <td className="py-4 px-4 text-right">
                      <span
                        className={`font-['Inter'] text-sm font-medium ${bucket.cost !== null ? "text-brand-primary" : "text-gray-400"}`}
                      >
                        {formatCost(bucket.cost)}
                      </span>
                    </td>
                    <td className="py-4 px-4 text-right">
                      <span className="font-['Inter'] text-sm text-gray-500">
                        {bucket.p50_ms.toLocaleString()}ms
                      </span>
                    </td>
                    <td className="py-4 px-4 text-right">
                      <span className="font-['Inter'] text-sm text-gray-500">
                        {bucket.p95_ms.toLocaleString()}ms
                      </span>
                    </td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
        {!loading && buckets.length === 0 && (
          <EmptyState
            emoji="📊"
            title="No usage recorded in this window"
            description="If calls are being made, check that LLM_USAGE_TRACKING_ENABLED is set."
          />
        )}
      </div>
    </div>
  );
}
