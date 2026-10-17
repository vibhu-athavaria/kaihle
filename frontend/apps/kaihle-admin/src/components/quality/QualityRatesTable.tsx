import { Badge, EmptyState, Skeleton } from "@kaihle/ui";
import type { QualityRateRow } from "../../hooks/useAdminQuality";

interface QualityRatesTableProps {
  rates: QualityRateRow[];
  loading: boolean;
  showWeek: boolean;
  truncated: boolean;
}

const HEADER =
  "text-left py-3 px-4 font-['Inter'] text-xs uppercase tracking-wide text-gray-400";

function pct(value: number | null): string {
  return value === null ? "—" : `${(value * 100).toFixed(1)}%`;
}

function formatWeek(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  });
}

function humanise(status: string): string {
  const lower = status.toLowerCase().replace(/_/g, " ");
  return lower.charAt(0).toUpperCase() + lower.slice(1);
}

function RubricLabel({ row }: { row: QualityRateRow }) {
  if (row.is_indicative) {
    // Judge agreement with humans is not established: never present as a trusted rate.
    return <Badge variant="warning">Indicative</Badge>;
  }
  if (row.rubric_status)
    return <Badge variant="info">{humanise(row.rubric_status)}</Badge>;
  return <Badge variant="neutral">Deterministic</Badge>;
}

export function QualityRatesTable({
  rates,
  loading,
  showWeek,
  truncated,
}: QualityRatesTableProps) {
  const columns = showWeek ? 7 : 6;
  return (
    <div className="bg-white rounded-2xl border border-gray-200 overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full">
          <caption className="sr-only">
            Pass rate per task and check, with sample size and 95% Wilson
            interval
          </caption>
          <thead>
            <tr className="bg-gray-50 border-b border-gray-200">
              {showWeek && <th className={HEADER}>Week of</th>}
              <th className={HEADER}>Task</th>
              <th className={HEADER}>Check</th>
              <th className={HEADER}>Type</th>
              <th className={HEADER}>Pass rate</th>
              <th className={HEADER}>Sample</th>
              <th className={HEADER}>Indeterminate</th>
            </tr>
          </thead>
          <tbody>
            {loading &&
              [...Array(5)].map((_, i) => (
                <tr key={i} className="border-b border-gray-50">
                  {[...Array(columns)].map((__, j) => (
                    <td key={j} className="py-3 px-4">
                      <Skeleton className="h-4 w-20" />
                    </td>
                  ))}
                </tr>
              ))}
            {!loading &&
              rates.map((r) => (
                <tr
                  key={`${r.week_start}-${r.task}-${r.check_name}-${r.rubric_status}`}
                  className="border-b border-gray-50"
                >
                  {showWeek && (
                    <td className="py-3 px-4 font-['Inter'] text-sm text-gray-500 whitespace-nowrap">
                      {formatWeek(r.week_start)}
                    </td>
                  )}
                  <td className="py-3 px-4 font-['Inter'] text-sm font-medium text-gray-700">
                    {r.task}
                  </td>
                  <td className="py-3 px-4 font-['Inter'] text-sm text-gray-700">
                    {r.check_name}
                  </td>
                  <td className="py-3 px-4">
                    <RubricLabel row={r} />
                  </td>
                  <td className="py-3 px-4 font-['Inter'] text-sm">
                    {r.pass_rate === null ? (
                      <span className="text-gray-500">No measurable data</span>
                    ) : (
                      <div>
                        <span className="font-semibold text-brand-ink">
                          {pct(r.pass_rate)}
                        </span>
                        <span className="block text-xs text-gray-500">
                          {`95% CI ${pct(r.ci_low)}–${pct(r.ci_high)}`}
                        </span>
                      </div>
                    )}
                  </td>
                  <td className="py-3 px-4 font-['Inter'] text-sm text-gray-600 whitespace-nowrap">
                    {`n = ${r.n}`}
                  </td>
                  <td className="py-3 px-4 font-['Inter'] text-sm text-gray-500 whitespace-nowrap">
                    {`${r.indeterminate} indeterminate`}
                  </td>
                </tr>
              ))}
          </tbody>
        </table>
      </div>

      {!loading && rates.length === 0 && (
        <EmptyState
          emoji="📊"
          title="No evaluation results yet"
          description="Results appear here once a production evaluation has run. Set a budget above and enable at least one task first."
        />
      )}

      {!loading && truncated && (
        <p className="px-4 py-3 border-t border-gray-200 font-['Inter'] text-xs text-gray-500">
          Results were truncated. Filter by task to see every row.
        </p>
      )}
    </div>
  );
}
