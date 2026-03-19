import { Link } from "react-router-dom";
import { AdminLayout } from "@kaihle/ui";
import { Card, Badge, Button, Skeleton } from "@kaihle/ui";
import { useAuth } from "@kaihle/auth";
import {
  usePlatformStats,
  useAdminSchools,
  useRecentActivity,
} from "../../hooks/useKaihleAdmin";
import {
  School,
  RecentActivity as RecentActivityType,
} from "../../hooks/useKaihleAdmin";
import { TrendingUp, Users, DollarSign, Activity } from "lucide-react";

function KPICard({
  icon,
  label,
  value,
  valueColor = "text-role-admin-ink",
  loading,
}: {
  icon: React.ReactNode;
  label: string;
  value: string | number;
  valueColor?: string;
  loading?: boolean;
}) {
  if (loading) {
    return (
      <Card className="bg-white border border-role-admin-border">
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-gray-100 flex items-center justify-center">
            <Skeleton className="w-6 h-6 rounded" />
          </div>
          <div>
            <Skeleton className="h-3 w-16 mb-2" />
            <Skeleton className="h-6 w-12" />
          </div>
        </div>
      </Card>
    );
  }
  return (
    <Card className="bg-white border border-role-admin-border">
      <div className="flex items-center gap-4">
        <div className="w-12 h-12 rounded-xl bg-brand-light flex items-center justify-center text-brand-primary">
          {icon}
        </div>
        <div>
          <p className="text-xs font-bold uppercase tracking-widest text-role-admin-muted">
            {label}
          </p>
          <p className={`text-2xl font-bold ${valueColor}`}>{value}</p>
        </div>
      </div>
    </Card>
  );
}

function getTrialBadgeVariant(
  daysRemaining: number | null,
): "danger" | "warning" | "neutral" {
  if (daysRemaining === null) return "neutral";
  if (daysRemaining < 3) return "danger";
  if (daysRemaining < 7) return "warning";
  return "neutral";
}

function getDaysRemaining(trialEndDate: string | null): number | null {
  if (!trialEndDate) return null;
  const end = new Date(trialEndDate);
  const now = new Date();
  const diff = Math.ceil(
    (end.getTime() - now.getTime()) / (1000 * 60 * 60 * 24),
  );
  return diff > 0 ? diff : 0;
}

function SchoolStatusTable({
  schools,
  loading,
}: {
  schools: School[];
  loading?: boolean;
}) {
  if (loading) {
    return (
      <div className="space-y-3">
        {[...Array(4)].map((_, i) => (
          <div
            key={i}
            className="flex items-center gap-4 p-4 border border-role-admin-border rounded-xl"
          >
            <Skeleton className="h-4 w-32" />
            <Skeleton className="h-4 w-20" />
            <Skeleton className="h-4 w-16" />
            <Skeleton className="h-4 w-12" />
          </div>
        ))}
      </div>
    );
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full">
        <thead>
          <tr className="border-b border-role-admin-border">
            <th className="text-left py-3 px-4 text-xs font-bold uppercase tracking-widest text-role-admin-muted">
              Name
            </th>
            <th className="text-left py-3 px-4 text-xs font-bold uppercase tracking-widest text-role-admin-muted">
              Status
            </th>
            <th className="text-left py-3 px-4 text-xs font-bold uppercase tracking-widest text-role-admin-muted">
              Plan
            </th>
            <th className="text-left py-3 px-4 text-xs font-bold uppercase tracking-widest text-role-admin-muted">
              Expiry
            </th>
          </tr>
        </thead>
        <tbody>
          {schools.map((school) => {
            const daysRemaining = getDaysRemaining(school.trial_end_date);
            const badgeVariant =
              school.subscription_status === "ACTIVE"
                ? "success"
                : school.subscription_status === "TRIAL"
                  ? getTrialBadgeVariant(daysRemaining)
                  : "danger";
            return (
              <tr
                key={school.id}
                className="border-b border-role-admin-border hover:bg-gray-50 transition-colors"
              >
                <td className="py-3 px-4">
                  <Link
                    to={`/kaihle-admin/schools/${school.id}`}
                    className="text-sm font-semibold text-role-admin-ink hover:text-brand-primary"
                  >
                    {school.name}
                  </Link>
                </td>
                <td className="py-3 px-4">
                  <Badge variant={badgeVariant}>
                    {school.subscription_status}
                  </Badge>
                </td>
                <td className="py-3 px-4 text-sm text-role-admin-subtle">
                  {school.plan_tier}
                </td>
                <td className="py-3 px-4 text-sm text-role-admin-subtle">
                  {school.subscription_status === "TRIAL" &&
                  school.trial_end_date
                    ? `${daysRemaining}d`
                    : "—"}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function RecentActivityList({ loading }: { loading?: boolean }) {
  const { data: activities } = useRecentActivity();
  if (loading || !activities) {
    return (
      <div className="space-y-3">
        {[...Array(3)].map((_, i) => (
          <div key={i} className="flex items-start gap-3">
            <Skeleton className="w-2 h-2 rounded-full mt-2" />
            <div className="flex-1">
              <Skeleton className="h-4 w-48 mb-1" />
              <Skeleton className="h-3 w-24" />
            </div>
          </div>
        ))}
      </div>
    );
  }
  return (
    <div className="space-y-3">
      {activities.slice(0, 10).map((activity: RecentActivityType) => (
        <div key={activity.id} className="flex items-start gap-3">
          <span className="w-2 h-2 rounded-full bg-brand-primary mt-2 flex-shrink-0" />
          <div>
            <p className="text-sm text-role-admin-ink">{activity.message}</p>
            <p className="text-xs text-role-admin-muted">
              {new Date(activity.timestamp).toLocaleString()}
            </p>
          </div>
        </div>
      ))}
      {activities.length === 0 && (
        <p className="text-sm text-role-admin-muted">No recent activity</p>
      )}
    </div>
  );
}

export function AdminOverview() {
  const { logout } = useAuth();
  const { data: stats, isLoading: statsLoading } = usePlatformStats();
  const { data: schoolsData, isLoading: schoolsLoading } = useAdminSchools({
    page_size: 50,
  });

  const schools = schoolsData?.schools ?? [];
  const formatCurrency = (amount: number) =>
    new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: "USD",
      maximumFractionDigits: 0,
    }).format(amount);

  return (
    <AdminLayout
      pageTitle="Platform overview"
      onLogout={logout}
      topNavAction={
        <Link to="/kaihle-admin/schools?action=create">
          <Button>+ Add school</Button>
        </Link>
      }
    >
      <div className="space-y-6">
        <section>
          <h2 className="text-xs font-bold uppercase tracking-widest text-role-admin-muted mb-4">
            Platform KPIs
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <KPICard
              icon={<TrendingUp className="w-6 h-6" />}
              label="Schools"
              value={stats?.total_schools ?? 0}
              loading={statsLoading}
            />
            <KPICard
              icon={<Users className="w-6 h-6" />}
              label="Students"
              value={stats?.total_students ?? 0}
              loading={statsLoading}
            />
            <KPICard
              icon={<DollarSign className="w-6 h-6" />}
              label="MRR"
              value={formatCurrency(stats?.mrr ?? 0)}
              valueColor="text-brand-primary"
              loading={statsLoading}
            />
          </div>
        </section>

        <section>
          <Card className="bg-white border border-role-admin-border">
            <div className="flex items-center gap-2 mb-4">
              <Activity className="w-5 h-5 text-role-admin-muted" />
              <span className="text-sm font-semibold text-role-admin-ink">
                Uptime: {stats?.uptime ?? "—"}% | Latency:{" "}
                {stats?.latency_ms ?? "—"}ms
              </span>
            </div>
          </Card>
        </section>

        <section>
          <h2 className="text-xs font-bold uppercase tracking-widest text-role-admin-muted mb-4">
            School status
          </h2>
          <Card className="bg-white border border-role-admin-border p-0 overflow-hidden">
            <SchoolStatusTable schools={schools} loading={schoolsLoading} />
          </Card>
        </section>

        <section>
          <h2 className="text-xs font-bold uppercase tracking-widest text-role-admin-muted mb-4">
            Recent activity
          </h2>
          <Card className="bg-white border border-role-admin-border">
            <RecentActivityList loading={schoolsLoading} />
          </Card>
        </section>
      </div>
    </AdminLayout>
  );
}
