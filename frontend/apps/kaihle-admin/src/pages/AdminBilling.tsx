import { AdminLayout } from "@kaihle/ui";
import { useAuth } from "@kaihle/auth";
import { useAdminBilling } from "../hooks/useAdminBilling";
import { RevenueKPIRow } from "../components/billing/RevenueKPIRow";
import { SubscriptionsTable } from "../components/billing/SubscriptionsTable";

export function AdminBilling() {
  const { logout } = useAuth();
  const { data, isLoading } = useAdminBilling();

  const subscriptions = data?.subscriptions ?? [];
  const summary = data?.summary;

  return (
    <AdminLayout pageTitle="Platform billing" onLogout={logout}>
      <div className="space-y-6">
        {/* KPI Section */}
        <section>
          <h2 className="font-inter text-xs font-bold uppercase tracking-widest text-gray-400 mb-4">
            Revenue overview
          </h2>
          <RevenueKPIRow summary={summary} loading={isLoading} />
        </section>

        {/* Subscriptions Table Section */}
        <section>
          <h2 className="font-inter text-xs font-bold uppercase tracking-widest text-gray-400 mb-4">
            All subscriptions
          </h2>
          <SubscriptionsTable
            subscriptions={subscriptions}
            loading={isLoading}
          />
        </section>
      </div>
    </AdminLayout>
  );
}
