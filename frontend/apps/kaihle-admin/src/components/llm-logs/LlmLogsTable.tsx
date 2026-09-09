import { Skeleton, EmptyState } from "@kaihle/ui";
import { LlmLogSummary } from "../../hooks/useAdminLlmLogs";
import { formatCost } from "../../utils/formatCost";

interface LlmLogsTableProps {
  logs: LlmLogSummary[];
  loading: boolean;
  currentPage: number;
  totalPages: number;
  onPageChange: (page: number) => void;
  onRowClick: (log: LlmLogSummary) => void;
}

function formatTimestamp(iso: string): string {
  return new Date(iso).toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

export function LlmLogsTable({
  logs,
  loading,
  currentPage,
  totalPages,
  onPageChange,
  onRowClick,
}: LlmLogsTableProps) {
  return (
    <div className="bg-white rounded-2xl border border-gray-200 overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="bg-gray-50 border-b border-gray-200">
              <th className="text-left py-3 px-4 font-['Inter'] text-xs uppercase tracking-wide text-gray-400">
                Time
              </th>
              <th className="text-left py-3 px-4 font-['Inter'] text-xs uppercase tracking-wide text-gray-400">
                Task
              </th>
              <th className="text-left py-3 px-4 font-['Inter'] text-xs uppercase tracking-wide text-gray-400">
                Model
              </th>
              <th className="text-left py-3 px-4 font-['Inter'] text-xs uppercase tracking-wide text-gray-400">
                Component
              </th>
              <th className="text-right py-3 px-4 font-['Inter'] text-xs uppercase tracking-wide text-gray-400">
                Tokens (in/out)
              </th>
              <th className="text-right py-3 px-4 font-['Inter'] text-xs uppercase tracking-wide text-gray-400">
                Latency
              </th>
              <th className="text-right py-3 px-4 font-['Inter'] text-xs uppercase tracking-wide text-gray-400">
                Cost
              </th>
              <th className="text-left py-3 px-4 font-['Inter'] text-xs uppercase tracking-wide text-gray-400">
                Status
              </th>
            </tr>
          </thead>
          <tbody>
            {loading &&
              [...Array(8)].map((_, i) => (
                <tr key={i} className="border-b border-gray-50">
                  {[...Array(8)].map((__, j) => (
                    <td key={j} className="py-4 px-4">
                      <Skeleton className="h-4 w-16" />
                    </td>
                  ))}
                </tr>
              ))}
            {!loading &&
              logs.map((log) => (
                <tr
                  key={log.id}
                  onClick={() => onRowClick(log)}
                  className="border-b border-gray-50 hover:bg-gray-50 cursor-pointer transition-colors duration-75"
                >
                  <td className="py-4 px-4">
                    <span className="font-['Inter'] text-sm text-gray-500">
                      {formatTimestamp(log.created_at)}
                    </span>
                  </td>
                  <td className="py-4 px-4">
                    <span className="font-['Inter'] text-sm font-medium text-gray-700">
                      {log.task}
                    </span>
                  </td>
                  <td className="py-4 px-4">
                    <span className="font-['Inter'] text-sm text-gray-600">
                      {log.model}
                    </span>
                  </td>
                  <td className="py-4 px-4">
                    <span className="font-['Inter'] text-sm text-gray-500">
                      {log.component ?? "—"}
                    </span>
                  </td>
                  <td className="py-4 px-4 text-right">
                    <span className="font-['Inter'] text-sm text-gray-600">
                      {log.prompt_tokens ?? "—"} /{" "}
                      {log.completion_tokens ?? "—"}
                    </span>
                  </td>
                  <td className="py-4 px-4 text-right">
                    <span className="font-['Inter'] text-sm text-gray-500">
                      {log.latency_ms.toLocaleString()}ms
                    </span>
                  </td>
                  <td className="py-4 px-4 text-right">
                    <span
                      className={`font-['Inter'] text-sm font-medium ${log.estimated_cost_usd !== null ? "text-brand-primary" : "text-gray-400"}`}
                    >
                      {formatCost(log.estimated_cost_usd)}
                    </span>
                  </td>
                  <td className="py-4 px-4">
                    {log.succeeded ? (
                      <span className="inline-flex rounded-full px-2.5 py-1 text-xs font-medium bg-green-50 text-green-700">
                        OK
                      </span>
                    ) : (
                      <span
                        className="inline-flex rounded-full px-2.5 py-1 text-xs font-medium bg-red-50 text-red-700"
                        title={log.error_type ?? undefined}
                      >
                        {log.error_type ?? "Failed"}
                      </span>
                    )}
                  </td>
                </tr>
              ))}
          </tbody>
        </table>
      </div>

      {!loading && logs.length === 0 && (
        <EmptyState
          emoji="🪵"
          title="No LLM calls recorded"
          description="If calls are being made, check that LLM_USAGE_TRACKING_ENABLED is set."
        />
      )}

      {!loading && logs.length > 0 && totalPages > 1 && (
        <div className="px-4 py-3 border-t border-gray-200 flex items-center justify-between">
          <span className="font-['Inter'] text-sm text-gray-600">
            Page {currentPage} of {totalPages}
          </span>
          <div className="flex gap-2">
            <button
              onClick={() => onPageChange(currentPage - 1)}
              disabled={currentPage === 1}
              className="px-3 py-1.5 border border-gray-200 rounded-lg text-sm font-['Inter'] text-gray-600 hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed min-h-[36px]"
            >
              Previous
            </button>
            <button
              onClick={() => onPageChange(currentPage + 1)}
              disabled={currentPage === totalPages}
              className="px-3 py-1.5 border border-gray-200 rounded-lg text-sm font-['Inter'] text-gray-600 hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed min-h-[36px]"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
