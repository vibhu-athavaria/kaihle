import { useState, useEffect } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { AdminLayout } from "@kaihle/ui";
import { Card, Badge, Button, Skeleton } from "@kaihle/ui";
import { useAuth } from "@kaihle/auth";
import { useAdminSchools } from "../../hooks/useKaihleAdmin";
import { School } from "../../hooks/useKaihleAdmin";
import { Plus, Filter } from "lucide-react";
import { AdminCreateSchoolModal } from "./AdminCreateSchoolModal";

type FilterTab = "ALL" | "ACTIVE" | "TRIAL" | "SUSPENDED";

const filterTabs: { key: FilterTab; label: string }[] = [
  { key: "ALL", label: "All" },
  { key: "ACTIVE", label: "Active" },
  { key: "TRIAL", label: "Trial" },
  { key: "SUSPENDED", label: "Suspended" },
];

function getStatusBadgeVariant(
  status: School["subscription_status"],
): "success" | "warning" | "danger" | "neutral" {
  switch (status) {
    case "ACTIVE":
      return "success";
    case "TRIAL":
      return "warning";
    case "SUSPENDED":
      return "danger";
    default:
      return "neutral";
  }
}

function SchoolsTable({
  schools,
  loading,
}: {
  schools: School[];
  loading?: boolean;
}) {
  if (loading) {
    return (
      <div className="space-y-3">
        {[...Array(5)].map((_, i) => (
          <div
            key={i}
            className="flex items-center gap-4 p-4 border border-role-admin-border rounded-xl"
          >
            <Skeleton className="h-4 w-40" />
            <Skeleton className="h-4 w-20" />
            <Skeleton className="h-4 w-20" />
            <Skeleton className="h-4 w-20" />
          </div>
        ))}
      </div>
    );
  }
  if (schools.length === 0) {
    return (
      <div className="text-center py-12">
        <p className="text-role-admin-muted">No schools found</p>
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
              Plan
            </th>
            <th className="text-left py-3 px-4 text-xs font-bold uppercase tracking-widest text-role-admin-muted">
              Status
            </th>
            <th className="text-left py-3 px-4 text-xs font-bold uppercase tracking-widest text-role-admin-muted">
              Created
            </th>
          </tr>
        </thead>
        <tbody>
          {schools.map((school) => (
            <tr
              key={school.id}
              className="border-b border-role-admin-border hover:bg-gray-50 transition-colors cursor-pointer"
            >
              <td className="py-3 px-4">
                <Link
                  to={`/kaihle-admin/schools/${school.id}`}
                  className="text-sm font-semibold text-role-admin-ink hover:text-brand-primary"
                >
                  {school.name}
                </Link>
                {school.country && (
                  <span className="text-xs text-role-admin-muted ml-2">
                    {school.country}
                    {school.city && `, ${school.city}`}
                  </span>
                )}
              </td>
              <td className="py-3 px-4 text-sm text-role-admin-subtle">
                {school.plan_tier}
              </td>
              <td className="py-3 px-4">
                <Badge
                  variant={getStatusBadgeVariant(school.subscription_status)}
                >
                  {school.subscription_status}
                </Badge>
              </td>
              <td className="py-3 px-4 text-sm text-role-admin-subtle">
                {new Date(school.created_at).toLocaleDateString()}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function AdminSchools() {
  const { logout } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();
  const [activeFilter, setActiveFilter] = useState<FilterTab>("ALL");
  const [showCreateModal, setShowCreateModal] = useState(false);

  useEffect(() => {
    if (searchParams.get("action") === "create") {
      setShowCreateModal(true);
      searchParams.delete("action");
      setSearchParams(searchParams);
    }
  }, [searchParams, setSearchParams]);

  const { data: schoolsData, isLoading } = useAdminSchools({
    page_size: 50,
    status: activeFilter === "ALL" ? undefined : activeFilter,
  });

  const schools = schoolsData?.schools ?? [];

  return (
    <AdminLayout
      pageTitle="Schools"
      onLogout={logout}
      topNavAction={
        <Button
          onClick={() => setShowCreateModal(true)}
          icon={<Plus className="w-4 h-4" />}
        >
          Add school
        </Button>
      }
    >
      <div className="space-y-6">
        <div className="flex items-center gap-2 border-b border-role-admin-border pb-4">
          <Filter className="w-4 h-4 text-role-admin-muted" />
          <div className="flex gap-1">
            {filterTabs.map((tab) => (
              <button
                key={tab.key}
                onClick={() => setActiveFilter(tab.key)}
                className={[
                  "px-4 py-2 text-sm font-semibold rounded-lg transition-colors",
                  activeFilter === tab.key
                    ? "bg-brand-primary text-white"
                    : "text-role-admin-subtle hover:bg-gray-100",
                ].join(" ")}
              >
                {tab.label}
              </button>
            ))}
          </div>
        </div>

        <Card className="bg-white border border-role-admin-border p-0 overflow-hidden">
          <SchoolsTable schools={schools} loading={isLoading} />
        </Card>
      </div>

      {showCreateModal && (
        <AdminCreateSchoolModal onClose={() => setShowCreateModal(false)} />
      )}
    </AdminLayout>
  );
}
