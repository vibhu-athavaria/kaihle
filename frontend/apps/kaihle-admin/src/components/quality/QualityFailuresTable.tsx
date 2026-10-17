import { Button, EmptyState, Skeleton } from "@kaihle/ui";
import type { QualityFailure } from "../../hooks/useAdminQuality";

interface QualityFailuresTableProps {
  failures: QualityFailure[];
  loading: boolean;
  page: number;
  totalPages: number;
  onPageChange: (page: number) => void;
  onOpenLog: (usageEventId: string) => void;
}

const HEADER =
  "text-left py-3 px-4 font-['Inter'] text-xs uppercase tracking-wide text-gray-400";

function formatTimestamp(iso: string): string {
  return new Date(iso).toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function QualityFailuresTable({
  failures,
  loading,
  page,
  totalPages,
  onPageChange,
  onOpenLog,
}: QualityFailuresTableProps) {
  return (
    <div className="bg-white rounded-2xl border border-gray-200 overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full">
          <caption className="sr-only">Failing checks, newest first</caption>
          <thead>
            <tr className="bg-gray-50 border-b border-gray-200">
              <th className={HEADER}>Time</th>
              <th className={HEADER}>Task</th>
              <th className={HEADER}>Failed check</th>
              <th className={HEADER}>LLM log</th>
            </tr>
          </thead>
          <tbody>
            {loading &&
              [...Array(4)].map((_, i) => (
                <tr key={i} className="border-b border-gray-50">
                  {[...Array(4)].map((__, j) => (
                    <td key={j} className="py-3 px-4">
                      <Skeleton className="h-4 w-20" />
                    </td>
                  ))}
                </tr>
              ))}
            {!loading &&
              failures.map((f) => (
                <tr
                  key={`${f.usage_event_id}-${f.check_name}`}
                  className="border-b border-gray-50"
                >
                  <td className="py-2 px-4 font-['Inter'] text-sm text-gray-500 whitespace-nowrap">
                    {formatTimestamp(f.created_at)}
                  </td>
                  <td className="py-2 px-4 font-['Inter'] text-sm font-medium text-gray-700">
                    {f.task}
                  </td>
                  <td className="py-2 px-4 font-['Inter'] text-sm text-gray-700">
                    {f.check_name}
                  </td>
                  <td className="py-2 px-4">
                    <Button
                      variant="secondary"
                      size="sm"
                      className="font-['Inter'] min-h-[44px]"
                      aria-label={`Open LLM log ${f.usage_event_id}`}
                      onClick={() => onOpenLog(f.usage_event_id)}
                    >
                      View log
                    </Button>
                  </td>
                </tr>
              ))}
          </tbody>
        </table>
      </div>

      {!loading && failures.length === 0 && (
        <EmptyState
          emoji="✅"
          title="No failing checks"
          description="Nothing in the current window failed a check, or no evaluation has run yet."
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
