import { Skeleton, EmptyState } from "@kaihle/ui";
import { ArrowUpDown, ArrowUp, ArrowDown } from "lucide-react";
import {
  LlmLogSummary,
  LlmLogFilterOptions,
  LlmLogSortBy,
  LlmLogSortDir,
} from "../../hooks/useAdminLlmLogs";
import { formatCost } from "../../utils/formatCost";

interface LlmLogsTableProps {
  logs: LlmLogSummary[];
  loading: boolean;
  currentPage: number;
  totalPages: number;
  onPageChange: (page: number) => void;
  onRowClick: (log: LlmLogSummary) => void;
  sortBy: LlmLogSortBy;
  sortDir: LlmLogSortDir;
  onSortChange: (sortBy: LlmLogSortBy) => void;
  filterOptions: LlmLogFilterOptions | undefined;
  taskFilter: string;
  modelFilter: string;
  onTaskFilterChange: (task: string) => void;
  onModelFilterChange: (model: string) => void;
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

interface SortHeaderProps {
  field: LlmLogSortBy;
  label: string;
  align?: "left" | "right";
  sortBy: LlmLogSortBy;
  sortDir: LlmLogSortDir;
  onSortChange: (field: LlmLogSortBy) => void;
}

function SortHeader({
  field,
  label,
  align = "left",
  sortBy,
  sortDir,
  onSortChange,
}: SortHeaderProps) {
  const isActive = sortBy === field;
  return (
    <button
      onClick={() => onSortChange(field)}
      className={`flex items-center gap-1 font-['Inter'] text-xs uppercase tracking-wide text-gray-400 hover:text-gray-600 transition-colors focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2 rounded ${
        align === "right" ? "ml-auto" : ""
      }`}
      aria-label={`Sort by ${label}`}
    >
      {label}
      {isActive ? (
        sortDir === "asc" ? (
          <ArrowUp className="w-3 h-3 text-brand-primary" aria-hidden="true" />
        ) : (
          <ArrowDown
            className="w-3 h-3 text-brand-primary"
            aria-hidden="true"
          />
        )
      ) : (
        <ArrowUpDown className="w-3 h-3 text-gray-300" aria-hidden="true" />
      )}
    </button>
  );
}

export function LlmLogsTable({
  logs,
  loading,
  currentPage,
  totalPages,
  onPageChange,
  onRowClick,
  sortBy,
  sortDir,
  onSortChange,
  filterOptions,
  taskFilter,
  modelFilter,
  onTaskFilterChange,
  onModelFilterChange,
}: LlmLogsTableProps) {
  return (
    <div className="space-y-3">
      <div className="flex items-center gap-4 flex-wrap">
        <div className="flex items-center gap-2">
          <label
            htmlFor="llm-logs-task-filter"
            className="font-['Inter'] text-xs uppercase tracking-wide text-gray-400"
          >
            Task
          </label>
          <select
            id="llm-logs-task-filter"
            value={taskFilter}
            onChange={(e) => onTaskFilterChange(e.target.value)}
            className="font-['Inter'] text-sm border border-gray-200 rounded-lg px-3 py-1.5 text-gray-700 focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2"
          >
            <option value="">All tasks</option>
            {(filterOptions?.tasks ?? []).map((task) => (
              <option key={task} value={task}>
                {task}
              </option>
            ))}
          </select>
        </div>

        <div className="flex items-center gap-2">
          <label
            htmlFor="llm-logs-model-filter"
            className="font-['Inter'] text-xs uppercase tracking-wide text-gray-400"
          >
            Model
          </label>
          <select
            id="llm-logs-model-filter"
            value={modelFilter}
            onChange={(e) => onModelFilterChange(e.target.value)}
            className="font-['Inter'] text-sm border border-gray-200 rounded-lg px-3 py-1.5 text-gray-700 focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2"
          >
            <option value="">All models</option>
            {(filterOptions?.models ?? []).map((model) => (
              <option key={model} value={model}>
                {model}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="bg-white rounded-2xl border border-gray-200 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="bg-gray-50 border-b border-gray-200">
                <th className="text-left py-3 px-4">
                  <SortHeader
                    field="created_at"
                    label="Time"
                    sortBy={sortBy}
                    sortDir={sortDir}
                    onSortChange={onSortChange}
                  />
                </th>
                <th className="text-left py-3 px-4">
                  <SortHeader
                    field="task"
                    label="Task"
                    sortBy={sortBy}
                    sortDir={sortDir}
                    onSortChange={onSortChange}
                  />
                </th>
                <th className="text-left py-3 px-4">
                  <SortHeader
                    field="model"
                    label="Model"
                    sortBy={sortBy}
                    sortDir={sortDir}
                    onSortChange={onSortChange}
                  />
                </th>
                <th className="text-left py-3 px-4 font-['Inter'] text-xs uppercase tracking-wide text-gray-400">
                  Component
                </th>
                <th className="text-right py-3 px-4">
                  <SortHeader
                    field="tokens"
                    label="Tokens (in/out)"
                    align="right"
                    sortBy={sortBy}
                    sortDir={sortDir}
                    onSortChange={onSortChange}
                  />
                </th>
                <th className="text-right py-3 px-4">
                  <SortHeader
                    field="latency_ms"
                    label="Latency"
                    align="right"
                    sortBy={sortBy}
                    sortDir={sortDir}
                    onSortChange={onSortChange}
                  />
                </th>
                <th className="text-right py-3 px-4">
                  <SortHeader
                    field="cost"
                    label="Cost"
                    align="right"
                    sortBy={sortBy}
                    sortDir={sortDir}
                    onSortChange={onSortChange}
                  />
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
                      <td key={j} className="py-2 px-4">
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
                    <td className="py-2 px-4 whitespace-nowrap">
                      <span className="font-['Inter'] text-sm text-gray-500">
                        {formatTimestamp(log.created_at)}
                      </span>
                    </td>
                    <td className="py-2 px-4 max-w-[140px]">
                      <span
                        className="font-['Inter'] text-sm font-medium text-gray-700 block truncate"
                        title={log.task}
                      >
                        {log.task}
                      </span>
                    </td>
                    <td className="py-2 px-4 max-w-[200px]">
                      <span
                        className="font-['Inter'] text-sm text-gray-600 block truncate"
                        title={log.model}
                      >
                        {log.model}
                      </span>
                    </td>
                    <td className="py-2 px-4 max-w-[220px]">
                      <span
                        className="font-['Inter'] text-sm text-gray-500 block truncate"
                        title={log.component ?? undefined}
                      >
                        {log.component ?? "—"}
                      </span>
                    </td>
                    <td className="py-2 px-4 text-right whitespace-nowrap">
                      <span className="font-['Inter'] text-sm text-gray-600">
                        {log.prompt_tokens ?? "—"} /{" "}
                        {log.completion_tokens ?? "—"}
                      </span>
                    </td>
                    <td className="py-2 px-4 text-right whitespace-nowrap">
                      <span className="font-['Inter'] text-sm text-gray-500">
                        {log.latency_ms.toLocaleString()}ms
                      </span>
                    </td>
                    <td className="py-2 px-4 text-right whitespace-nowrap">
                      <span
                        className={`font-['Inter'] text-sm font-medium ${log.estimated_cost_usd !== null ? "text-brand-primary" : "text-gray-400"}`}
                      >
                        {formatCost(log.estimated_cost_usd)}
                      </span>
                    </td>
                    <td className="py-2 px-4 whitespace-nowrap">
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
            description="If calls are being made, check that LLM_USAGE_TRACKING_ENABLED is set. If a filter is active, try clearing it."
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
    </div>
  );
}
