import { Skeleton } from "@kaihle/ui";
import { BillingSummary } from "../../hooks/useAdminBilling";
import { DollarSign, Building2, TrendingUp, AlertCircle } from "lucide-react";

interface RevenueKPIRowProps {
  summary: BillingSummary | undefined;
  loading: boolean;
}

function formatCurrency(amount: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(amount);
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
          <p className="font-inter text-[11px] uppercase tracking-widest text-gray-400">
            {label}
          </p>
          <p className={`font-inter text-2xl font-bold ${valueColor}`}>
            {value}
          </p>
        </div>
      </div>
    </div>
  );
}

export function RevenueKPIRow({ summary, loading }: RevenueKPIRowProps) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
      <KPICard
        icon={<DollarSign className="w-6 h-6" />}
        label="Total Revenue"
        value={summary ? formatCurrency(summary.total_revenue) : "—"}
        loading={loading}
      />
      <KPICard
        icon={<Building2 className="w-6 h-6" />}
        label="Active Schools"
        value={summary?.active_schools.toString() ?? "—"}
        valueColor="text-gray-700"
        loading={loading}
      />
      <KPICard
        icon={<TrendingUp className="w-6 h-6" />}
        label="MRR"
        value={summary ? formatCurrency(summary.mrr) : "—"}
        loading={loading}
      />
      <KPICard
        icon={<AlertCircle className="w-6 h-6" />}
        label="Past Due"
        value={summary?.past_due_count.toString() ?? "—"}
        valueColor={
          summary && summary.past_due_count > 0
            ? "text-red-600"
            : "text-gray-400"
        }
        loading={loading}
      />
    </div>
  );
}
