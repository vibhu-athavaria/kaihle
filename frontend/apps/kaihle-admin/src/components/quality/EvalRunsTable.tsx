import { Badge, Button, EmptyState, Skeleton } from "@kaihle/ui";
import type { EvalRun, EvalRunStatus } from "../../hooks/useAdminQuality";
import { formatCost } from "../../utils/formatCost";

interface EvalRunsTableProps {
  runs: EvalRun[];
  loading: boolean;
  error: boolean;
  page: number;
  totalPages: number;
  onPageChange: (page: number) => void;
}

const HEADER =
  "text-left py-3 px-4 font-['Inter'] text-xs uppercase tracking-wide text-gray-400";
const CELL = "py-2 px-4 font-['Inter'] text-sm text-gray-700 align-top";

const STATUS: Record<
  EvalRunStatus,
  {
    label: string;
    variant: "success" | "warning" | "danger" | "info" | "neutral";
  }
> = {
  pending: { label: "Pending", variant: "info" },
  running: { label: "Running", variant: "info" },
  completed: { label: "Completed", variant: "success" },
  failed: { label: "Failed", variant: "danger" },
  budget_exhausted: { label: "Budget exhausted", variant: "warning" },
  empty: { label: "Empty sample", variant: "neutral" },
};

function formatTimestamp(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatDay(iso: string): string {
  return new Date(iso).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
  });
}

function StatusBadge({ status }: { status: EvalRunStatus }) {
  const { label, variant } = STATUS[status];
  // The visible text carries the meaning; colour only reinforces it.
  return (
    <span className="font-['Inter']">
      <Badge
        variant={variant}
        pulse={status === "pending" || status === "running"}
      >
        {label}
      </Badge>
    </span>
  );
}

export function EvalRunsTable({
  runs,
  loading,
  error,
  page,
  totalPages,
  onPageChange,
}: EvalRunsTableProps) {
  return (
    <div className="bg-white rounded-2xl border border-gray-200 overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full">
          <caption className="sr-only">Evaluation runs, newest first</caption>
          <thead>
            <tr className="bg-gray-50 border-b border-gray-200">
              <th className={HEADER}>Task</th>
              <th className={HEADER}>Status</th>
              <th className={HEADER}>Window</th>
              <th className={HEADER}>Evaluated</th>
              <th className={HEADER}>Skipped</th>
              <th className={HEADER}>Spend</th>
              <th className={HEADER}>Created</th>
            </tr>
          </thead>
          <tbody>
            {loading &&
              [...Array(4)].map((_, i) => (
                <tr key={i} className="border-b border-gray-50">
                  {[...Array(7)].map((__, j) => (
                    <td key={j} className="py-3 px-4">
                      <Skeleton className="h-4 w-20" />
                    </td>
                  ))}
                </tr>
              ))}
            {!loading &&
              runs.map((run) => (
                <tr key={run.id} className="border-b border-gray-50">
                  <td className={CELL}>
                    <span className="font-medium">{run.task}</span>
                    <span className="block text-xs text-gray-500">
                      {run.trigger === "scheduled" ? "scheduled" : "manual"}
                    </span>
                  </td>
                  <td className={CELL}>
                    <StatusBadge status={run.status} />
                    {run.status === "failed" && run.error_type && (
                      <span className="block text-xs text-brand-red mt-1">
                        {run.error_type}
                      </span>
                    )}
                  </td>
                  <td className={`${CELL} whitespace-nowrap`}>
                    {formatDay(run.window_start)} to {formatDay(run.window_end)}
                  </td>
                  <td className={`${CELL} whitespace-nowrap`}>
                    {run.evaluated_count} of {run.sampled_count} evaluated
                  </td>
                  <td className={CELL}>
                    <span className="block">
                      {run.skipped_not_independent_count} not independent
                    </span>
                    <span className="block">
                      {run.skipped_scrub_failed_count} scrub failed
                    </span>
                    <span className="block">
                      {run.skipped_unsupported_count} unsupported
                    </span>
                  </td>
                  <td className={`${CELL} whitespace-nowrap`}>
                    {formatCost(Number(run.spend_usd))}
                  </td>
                  <td className={`${CELL} whitespace-nowrap text-gray-500`}>
                    {formatTimestamp(run.created_at)}
                    {run.completed_at && (
                      <span className="block text-xs">
                        done {formatTimestamp(run.completed_at)}
                      </span>
                    )}
                  </td>
                </tr>
              ))}
          </tbody>
        </table>
      </div>

      {error && !loading && (
        <p
          role="alert"
          className="font-['Inter'] text-sm text-brand-red px-4 py-6"
        >
          Could not load evaluation runs. Please try again.
        </p>
      )}

      {!loading && !error && runs.length === 0 && (
        <EmptyState
          emoji="🧪"
          title="No evaluation runs yet"
          description="Enable a task, set a budget above 0 and choose Run now. Runs also start weekly once a budget is set."
        />
      )}

      {!loading && totalPages > 1 && (
        <div className="px-4 py-3 border-t border-gray-200 flex items-center justify-between">
          <span className="font-['Inter'] text-sm text-gray-600">
            Page {page} of {totalPages}
          </span>
          <div className="flex gap-2">
            <Button
              variant="secondary"
              size="sm"
              className="font-['Inter'] min-h-[44px]"
              disabled={page === 1}
              onClick={() => onPageChange(page - 1)}
            >
              Previous
            </Button>
            <Button
              variant="secondary"
              size="sm"
              className="font-['Inter'] min-h-[44px]"
              disabled={page === totalPages}
              onClick={() => onPageChange(page + 1)}
            >
              Next
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
