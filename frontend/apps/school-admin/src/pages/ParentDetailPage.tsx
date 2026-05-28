import { useAuth } from "@kaihle/auth";
import { useParams, useNavigate } from "react-router-dom";
import { DashboardLayout } from "@kaihle/ui";
import { getMasteryStyle } from "@kaihle/types";
import { useParentDetail } from "../hooks/useSchoolAdmin";

function initials(first: string, last: string) {
  return `${first.charAt(0)}${last.charAt(0)}`.toUpperCase();
}

export function ParentDetailPage() {
  const { parentId } = useParams<{ parentId: string }>();
  const navigate = useNavigate();
  const { user, logout } = useAuth();

  const { data: parent, isLoading, isError } = useParentDetail(parentId ?? "");

  if (isLoading) {
    return (
      <DashboardLayout
        variant="school-admin"
        onLogout={logout}
        pageTitle="Parent"
        permissions={user?.permissions}
      >
        <div className="animate-pulse space-y-4">
          <div className="h-6 bg-role-school-border rounded-full w-1/3" />
          <div className="bg-white border border-role-school-border rounded-xl p-5 flex items-center gap-4">
            <div className="w-14 h-14 rounded-full bg-role-school-border flex-shrink-0" />
            <div className="space-y-2 flex-1">
              <div className="h-5 bg-role-school-border rounded-full w-1/4" />
              <div className="h-4 bg-role-school-border rounded-full w-1/3" />
            </div>
          </div>
          <div className="space-y-2">
            {[...Array(3)].map((_, i) => (
              <div key={i} className="h-12 bg-role-school-border rounded-lg" />
            ))}
          </div>
        </div>
      </DashboardLayout>
    );
  }

  if (isError || !parent) {
    return (
      <DashboardLayout
        variant="school-admin"
        onLogout={logout}
        pageTitle="Parent"
        permissions={user?.permissions}
      >
        <div className="flex items-center justify-center py-24 text-sm font-semibold text-brand-red font-sans">
          Failed to load parent details. Please go back and try again.
        </div>
      </DashboardLayout>
    );
  }

  const isActive = parent.is_active;
  const fullName = `${parent.first_name} ${parent.last_name}`;

  return (
    <DashboardLayout
      variant="school-admin"
      pageTitle={fullName}
      onLogout={logout}
      permissions={user?.permissions}
    >
      {/* Breadcrumb */}
      <nav
        className="flex items-center gap-1.5 text-xs text-brand-muted mb-5"
        aria-label="Breadcrumb"
      >
        <button
          onClick={() => navigate("/school-admin/users")}
          className="hover:text-brand-primary transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-1 rounded"
        >
          Users
        </button>
        <span aria-hidden="true">›</span>
        <button
          onClick={() => navigate("/school-admin/users?tab=parents")}
          className="hover:text-brand-primary transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-1 rounded"
        >
          Parents
        </button>
        <span aria-hidden="true">›</span>
        <span className="text-brand-ink font-semibold">{fullName}</span>
      </nav>

      {/* Profile card */}
      <div className="bg-white border border-role-school-border rounded-xl p-5 flex items-center gap-4 mb-6">
        <div
          className={`w-14 h-14 rounded-full flex items-center justify-center text-white text-xl font-black flex-shrink-0 ${isActive ? "bg-brand-primary" : "bg-gray-300"}`}
          aria-label={`${fullName} initials`}
        >
          {initials(parent.first_name, parent.last_name)}
        </div>
        <div className="flex-1 min-w-0">
          <h1 className="font-display font-bold text-xl text-brand-ink leading-tight">
            {fullName}
          </h1>
          <p className="text-sm text-brand-body mt-0.5 truncate">
            {parent.email}
          </p>
        </div>
        <div className="flex flex-col items-end gap-2 flex-shrink-0">
          {isActive ? (
            <span className="text-xs font-bold rounded-full px-2 py-px bg-[#f0fdf4] text-brand-green">
              Active
            </span>
          ) : (
            <span className="text-xs font-bold rounded-full px-2 py-px bg-gray-100 text-brand-muted">
              Inactive
            </span>
          )}
          <span className="text-xs text-brand-muted font-sans">
            {parent.linked_students.length}{" "}
            {parent.linked_students.length === 1
              ? "linked student"
              : "linked students"}
          </span>
        </div>
      </div>

      {/* Linked Students */}
      <p className="text-xs font-black uppercase tracking-[0.7px] text-role-school-muted mb-3">
        Linked Students
      </p>

      <div className="bg-white border border-role-school-border rounded-xl overflow-hidden">
        {parent.linked_students.length === 0 ? (
          <div className="py-12 text-center text-brand-muted text-sm">
            No linked students.
          </div>
        ) : (
          <table className="w-full border-collapse">
            <thead>
              <tr className="bg-[#fafcfa] border-b border-role-school-border">
                {["Student", "Classes", "Lowest Mastery", ""].map((h) => (
                  <th
                    key={h}
                    className="px-4 py-[10px] text-left text-xs font-black uppercase tracking-[0.7px] text-role-school-muted"
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {parent.linked_students.map((s) => {
                const { dotClass, label } = getMasteryStyle(s.worst_mastery);
                const handleNavigate = () =>
                  navigate(`/school-admin/users/students/${s.student_id}`);
                return (
                  <tr
                    key={s.student_id}
                    onClick={handleNavigate}
                    onKeyDown={(
                      e: React.KeyboardEvent<HTMLTableRowElement>,
                    ) => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault();
                        handleNavigate();
                      }
                    }}
                    tabIndex={0}
                    role="button"
                    aria-label={`View details for ${s.first_name} ${s.last_name}`}
                    className="border-b border-[#f0f5ee] last:border-0 cursor-pointer hover:bg-[#fafcfa] transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-inset"
                  >
                    <td className="px-4 py-[10px]">
                      <div className="flex items-center gap-2.5">
                        <div className="w-7 h-7 rounded-full flex items-center justify-center bg-brand-primary text-white text-xs font-black flex-shrink-0">
                          {initials(s.first_name, s.last_name)}
                        </div>
                        <span className="text-sm font-bold text-brand-ink">
                          {s.first_name} {s.last_name}
                        </span>
                      </div>
                    </td>
                    <td className="px-4 py-[10px] text-xs text-brand-body">
                      {s.class_count}{" "}
                      {s.class_count === 1 ? "class" : "classes"}
                    </td>
                    <td className="px-4 py-[10px]">
                      <div className="flex items-center gap-1.5">
                        <span
                          className={`w-2 h-2 rounded-full flex-shrink-0 ${dotClass}`}
                          aria-label={label}
                          role="img"
                        />
                        <span className="text-xs font-bold text-brand-ink">
                          {label}
                        </span>
                      </div>
                    </td>
                    <td className="px-4 py-[10px] text-brand-muted text-base">
                      ›
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </DashboardLayout>
  );
}
