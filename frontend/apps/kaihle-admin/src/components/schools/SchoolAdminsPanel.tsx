import { useState } from "react";
import { Card, Button, Badge, Skeleton } from "@kaihle/ui";
import { UserPlus, Mail } from "lucide-react";
import {
  useSchoolAdmins,
  useUpdateAdminPermissions,
  type SchoolAdmin,
} from "../../hooks/useKaihleAdmin";
import { InviteAdminModal } from "./InviteAdminModal";

// Resolve effective permission value — null permissions means default (true).
function resolvePermission(
  permissions: Record<string, boolean> | null,
  key: string,
): boolean {
  if (permissions === null) return true;
  return permissions[key] ?? true;
}

function PermissionToggle({
  label,
  enabled,
  loading,
  onChange,
}: {
  label: string;
  enabled: boolean;
  loading: boolean;
  onChange: (next: boolean) => void;
}) {
  return (
    <div className="flex items-center gap-2">
      <button
        type="button"
        role="switch"
        aria-checked={enabled}
        aria-label={`${label} access`}
        disabled={loading}
        onClick={() => onChange(!enabled)}
        className={[
          "relative inline-flex h-5 w-9 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent",
          "transition-colors duration-200 focus-visible:outline-none focus-visible:ring-2",
          "focus-visible:ring-brand-primary focus-visible:ring-offset-2",
          enabled ? "bg-brand-primary" : "bg-gray-200",
          loading ? "opacity-50 cursor-not-allowed" : "",
        ].join(" ")}
      >
        <span
          aria-hidden="true"
          className={[
            "pointer-events-none inline-block h-4 w-4 rounded-full bg-white shadow",
            "transform transition duration-200 ease-in-out",
            enabled ? "translate-x-4" : "translate-x-0",
          ].join(" ")}
        />
      </button>
      <span className="text-xs text-role-admin-subtle">{label}</span>
    </div>
  );
}

function AdminRow({
  admin,
  schoolId,
  isOnly,
}: {
  admin: SchoolAdmin;
  schoolId: string;
  isOnly: boolean;
}) {
  const updatePermissions = useUpdateAdminPermissions(schoolId);

  const billingEnabled = resolvePermission(admin.permissions, "billing");
  const userMgmtEnabled = resolvePermission(
    admin.permissions,
    "user_management",
  );

  const toggle = (key: string, next: boolean) => {
    const current = admin.permissions ?? {};
    updatePermissions.mutate({
      userId: admin.id,
      permissions: { ...current, [key]: next },
    });
  };

  return (
    <div className="flex items-center justify-between py-3 border-b border-role-admin-border last:border-0">
      <div className="flex items-center gap-3 min-w-0">
        <div className="w-8 h-8 rounded-full bg-gray-100 flex items-center justify-center flex-shrink-0">
          <span className="text-xs font-bold text-role-admin-subtle">
            {admin.first_name[0]}
            {admin.last_name[0]}
          </span>
        </div>
        <div className="min-w-0">
          <p className="text-sm font-semibold text-role-admin-ink truncate">
            {admin.first_name} {admin.last_name}
          </p>
          <p className="text-xs text-role-admin-muted truncate flex items-center gap-1">
            <Mail className="w-3 h-3 flex-shrink-0" aria-hidden="true" />
            {admin.email}
          </p>
        </div>
        {!admin.is_active && <Badge variant="neutral">Inactive</Badge>}
      </div>

      <div className="flex items-center gap-6 flex-shrink-0 ml-4">
        {isOnly ? (
          <p className="text-xs text-role-admin-muted italic">
            Primary admin — full access
          </p>
        ) : (
          <>
            <PermissionToggle
              label="Billing"
              enabled={billingEnabled}
              loading={updatePermissions.isPending}
              onChange={(next) => toggle("billing", next)}
            />
            <PermissionToggle
              label="User mgmt"
              enabled={userMgmtEnabled}
              loading={updatePermissions.isPending}
              onChange={(next) => toggle("user_management", next)}
            />
          </>
        )}
      </div>
    </div>
  );
}

export function SchoolAdminsPanel({
  schoolId,
  schoolName,
}: {
  schoolId: string;
  schoolName: string;
}) {
  const { data: admins, isLoading } = useSchoolAdmins(schoolId);
  const [showInvite, setShowInvite] = useState(false);

  return (
    <>
      <Card className="bg-white border border-role-admin-border">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-bold text-role-admin-ink">
            School Admins
          </h3>
          <Button
            variant="secondary"
            size="sm"
            onClick={() => setShowInvite(true)}
            className="min-h-[44px] gap-1.5"
          >
            <UserPlus className="w-4 h-4" aria-hidden="true" />
            Invite admin
          </Button>
        </div>

        {isLoading ? (
          <div className="space-y-3">
            {[...Array(2)].map((_, i) => (
              <div key={i} className="flex items-center gap-3 py-3">
                <Skeleton className="w-8 h-8 rounded-full" />
                <div className="flex-1 space-y-1.5">
                  <Skeleton className="h-3.5 w-32" />
                  <Skeleton className="h-3 w-48" />
                </div>
              </div>
            ))}
          </div>
        ) : !admins || admins.length === 0 ? (
          <div className="text-center py-8">
            <p className="text-sm text-role-admin-muted">
              No admins found for this school.
            </p>
          </div>
        ) : (
          <div>
            {admins.length > 1 && (
              <p className="text-xs text-role-admin-muted mb-3">
                Toggle permissions for co-admins. The first admin always has
                full access.
              </p>
            )}
            {admins.map((admin, idx) => (
              <AdminRow
                key={admin.id}
                admin={admin}
                schoolId={schoolId}
                isOnly={admins.length === 1 || idx === 0}
              />
            ))}
          </div>
        )}
      </Card>

      <InviteAdminModal
        schoolId={schoolId}
        schoolName={schoolName}
        open={showInvite}
        onClose={() => setShowInvite(false)}
      />
    </>
  );
}
