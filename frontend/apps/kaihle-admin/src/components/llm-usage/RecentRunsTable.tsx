import { Skeleton, EmptyState } from "@kaihle/ui";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { LlmUsageBucket } from "../../hooks/useAdminLlmUsage";
import { formatCost } from "../../utils/formatCost";

interface RecentRunsTableProps {
  runs: LlmUsageBucket[];
  loading: boolean;
  page: number;
  pageSize: number;
  totalRuns: number;
  onPageChange: (page: number) => void;
}

/**
 * A whole batch-script invocation as one row, so "what did the cambridge_v2 remap
 * adjudication cost" has a single number to point to. Genuinely paginated — `run_id`
 * groupings can far outnumber task/component/model groupings, and this codebase
 * prohibits an unbounded scan to render one table.
 *
 * Sorted by cost, not recency (it shares `summarise_usage`'s bucket query, which orders
 * by spend) — the page heading says "Runs by cost", not "Recent runs", so the label
 * matches what's actually shown.
 */
export function RecentRunsTable({
  runs,
  loading,
  page,
  pageSize,
  totalRuns,
  onPageChange,
}: RecentRunsTableProps) {
  const totalPages = Math.max(1, Math.ceil(totalRuns / pageSize));

  return (
    <div className="bg-white rounded-2xl border border-gray-200 overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="bg-gray-50 border-b border-gray-200">
              <th className="text-left py-3 px-4 font-['Inter'] text-xs uppercase tracking-wide text-gray-400">
                Run
              </th>
              <th className="text-right py-3 px-4 font-['Inter'] text-xs uppercase tracking-wide text-gray-400">
                Calls
              </th>
              <th className="text-right py-3 px-4 font-['Inter'] text-xs uppercase tracking-wide text-gray-400">
                Failures
              </th>
              <th className="text-right py-3 px-4 font-['Inter'] text-xs uppercase tracking-wide text-gray-400">
                Cost
              </th>
            </tr>
          </thead>
          <tbody>
            {loading &&
              [...Array(3)].map((_, i) => (
                <tr key={i} className="border-b border-gray-50">
                  {[...Array(4)].map((__, j) => (
                    <td key={j} className="py-4 px-4">
                      <Skeleton className="h-4 w-16" />
                    </td>
                  ))}
                </tr>
              ))}
            {!loading &&
              runs.map((run) => (
                <tr
                  key={run.bucket}
                  className="border-b border-gray-50 hover:bg-gray-50 transition-colors duration-75"
                >
                  <td className="py-4 px-4">
                    <span className="font-['Inter'] text-sm font-medium text-gray-700">
                      {run.bucket}
                    </span>
                  </td>
                  <td className="py-4 px-4 text-right">
                    <span className="font-['Inter'] text-sm text-gray-700">
                      {run.calls.toLocaleString()}
                    </span>
                  </td>
                  <td className="py-4 px-4 text-right">
                    <span
                      className={`font-['Inter'] text-sm ${run.failures > 0 ? "text-red-600" : "text-gray-400"}`}
                    >
                      {run.failures.toLocaleString()}
                    </span>
                  </td>
                  <td className="py-4 px-4 text-right">
                    <span
                      className={`font-['Inter'] text-sm font-medium ${run.cost !== null ? "text-brand-primary" : "text-gray-400"}`}
                    >
                      {formatCost(run.cost)}
                    </span>
                  </td>
                </tr>
              ))}
          </tbody>
        </table>
      </div>

      {!loading && runs.length === 0 && (
        <EmptyState
          emoji="🗂️"
          title="No batch runs recorded"
          description="Wrap batch scripts in usage_context.llm_component(name, run_id=...) to see them here."
        />
      )}

      {!loading && runs.length > 0 && (
        <div className="flex items-center justify-between px-4 py-3 border-t border-gray-100">
          <span className="font-['Inter'] text-xs text-gray-400">
            Page {page} of {totalPages} · {totalRuns.toLocaleString()} runs
          </span>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => onPageChange(page - 1)}
              disabled={page <= 1}
              aria-label="Previous page"
              className="min-h-[44px] min-w-[44px] flex items-center justify-center rounded-lg border border-gray-200 text-gray-500 disabled:opacity-40 disabled:cursor-not-allowed hover:bg-gray-50 focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2"
            >
              <ChevronLeft className="w-4 h-4" aria-hidden="true" />
            </button>
            <button
              type="button"
              onClick={() => onPageChange(page + 1)}
              disabled={page >= totalPages}
              aria-label="Next page"
              className="min-h-[44px] min-w-[44px] flex items-center justify-center rounded-lg border border-gray-200 text-gray-500 disabled:opacity-40 disabled:cursor-not-allowed hover:bg-gray-50 focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2"
            >
              <ChevronRight className="w-4 h-4" aria-hidden="true" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
