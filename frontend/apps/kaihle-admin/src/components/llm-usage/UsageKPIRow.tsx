import { Skeleton } from "@kaihle/ui";
import {
  DollarSign,
  Hash,
  AlertTriangle,
  ShieldAlert,
  Gauge,
} from "lucide-react";
import { LlmUsageSummary } from "../../hooks/useAdminLlmUsage";
import { formatCost } from "../../utils/formatCost";

interface UsageKPIRowProps {
  summary: LlmUsageSummary | undefined;
  loading: boolean;
}

interface KPICardProps {
  icon: React.ReactNode;
  label: string;
  value: string;
  valueColor?: string;
  loading?: boolean;
}

function KPICard({
  icon,
  label,
  value,
  valueColor = "text-brand-primary",
  loading,
}: KPICardProps) {
  if (loading) {
    return (
      <div className="bg-white rounded-2xl border border-gray-200 p-5">
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-gray-100 flex items-center justify-center">
            <Skeleton className="w-6 h-6 rounded" />
          </div>
          <div>
            <Skeleton className="h-3 w-16 mb-2" />
            <Skeleton className="h-6 w-20" />
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-2xl border border-gray-200 p-5">
      <div className="flex items-center gap-4">
        <div className="w-12 h-12 rounded-xl bg-gray-50 flex items-center justify-center text-gray-400">
          {icon}
        </div>
        <div>
          <p className="font-['Inter'] text-xs uppercase tracking-widest text-gray-400">
            {label}
          </p>
          <p className={`font-['Inter'] text-2xl font-bold ${valueColor}`}>
            {value}
          </p>
        </div>
      </div>
    </div>
  );
}

/**
 * The two honesty indicators (unpriced %, unattributed %) are KPI cards here, not a
 * footnote — they render even at 0%, per llm_cost_report.py's own stated principle that
 * a total silently omitting a share of calls is worse than no total at all.
 */
export function UsageKPIRow({ summary, loading }: UsageKPIRowProps) {
  const unpricedPercent = summary?.unpriced_percent ?? 0;
  const unattributedPercent = summary?.unattributed_percent ?? 0;

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
        <KPICard
          icon={<DollarSign className="w-6 h-6" aria-hidden="true" />}
          label="Total spend"
          value={summary ? formatCost(summary.cost) : "—"}
          loading={loading}
        />
        <KPICard
          icon={<Hash className="w-6 h-6" aria-hidden="true" />}
          label="Total calls"
          value={summary ? summary.calls.toLocaleString() : "—"}
          valueColor="text-gray-700"
          loading={loading}
        />
        <KPICard
          icon={<AlertTriangle className="w-6 h-6" aria-hidden="true" />}
          label="Unpriced"
          value={summary ? `${unpricedPercent.toFixed(1)}%` : "—"}
          valueColor={unpricedPercent > 0 ? "text-amber-600" : "text-gray-400"}
          loading={loading}
        />
        <KPICard
          icon={<ShieldAlert className="w-6 h-6" aria-hidden="true" />}
          label="Unattributed"
          value={summary ? `${unattributedPercent.toFixed(1)}%` : "—"}
          valueColor={
            unattributedPercent > 0 ? "text-amber-600" : "text-gray-400"
          }
          loading={loading}
        />
        <KPICard
          icon={<Gauge className="w-6 h-6" aria-hidden="true" />}
          label="p95 latency"
          value={summary ? `${summary.p95_ms.toLocaleString()}ms` : "—"}
          valueColor="text-gray-700"
          loading={loading}
        />
      </div>
      {summary && summary.unpriced_models.length > 0 && (
        <p className="font-['Inter'] text-xs text-gray-400">
          models: {summary.unpriced_models.join(", ")}
        </p>
      )}
    </div>
  );
}
