import { useState } from "react";
import { Link } from "react-router-dom";
import { DashboardLayout } from "@kaihle/ui";
import { Card } from "@kaihle/ui";
import { Badge } from "@kaihle/ui";
import { Button } from "@kaihle/ui";
import { useAuth } from "@kaihle/auth";
import { MoreVertical, Mail, UserX, UserCheck, RefreshCw } from "lucide-react";
import {
  useSchoolUsers,
  useInviteUser,
  useUpdateUser,
  type User,
} from "../../hooks/useSchoolAdmin";
import { InviteUserModal } from "./InviteUserModal";

type RoleTab = "TEACHER" | "STUDENT" | "PARENT";

const roleTabs: { value: RoleTab; label: string }[] = [
  { value: "TEACHER", label: "Teachers" },
  { value: "STUDENT", label: "Students" },
  { value: "PARENT", label: "Parents" },
];

function getStatusBadge(status: User["status"]) {
  switch (status) {
    case "ACTIVE":
      return <Badge variant="success">● Active</Badge>;
    case "INVITED":
      return (
        <Badge variant="gold" pulse>
          ○ Invited
        </Badge>
      );
    case "INACTIVE":
      return <Badge variant="danger">✕ Inactive</Badge>;
    default:
      return <Badge variant="neutral">{status}</Badge>;
  }
}

function getInitials(firstName: string, lastName: string): string {
  const first = firstName?.[0] || "";
  const last = lastName?.[0] || "";
  return (first + last).toUpperCase() || "?";
}

function UserRow({
  user,
  onResendInvite,
  onToggleStatus,
}: {
  user: User;
  onResendInvite: (user: User) => void;
  onToggleStatus: (user: User) => void;
}) {
  const [showMenu, setShowMenu] = useState(false);
  const initials = getInitials(user.first_name, user.last_name);

  return (
    <tr className="border-b border-brand-border-soft hover:bg-brand-light/30">
      <td className="py-3 px-4">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-full bg-brand-light text-brand-primary font-bold text-xs flex items-center justify-center">
            {initials}
          </div>
          <div>
            <p className="text-sm font-medium text-brand-ink">
              {user.first_name} {user.last_name}
            </p>
            <p className="text-xs text-brand-muted">{user.email}</p>
          </div>
        </div>
      </td>
      <td className="py-3 px-4">{getStatusBadge(user.status)}</td>
      <td className="py-3 px-4 relative">
        <button
          onClick={() => setShowMenu(!showMenu)}
          className="p-1 hover:bg-gray-100 rounded"
          aria-label="Actions"
        >
          <MoreVertical className="w-4 h-4 text-brand-muted" />
        </button>
        {showMenu && (
          <>
            <div className="fixed inset-0" onClick={() => setShowMenu(false)} />
            <div className="absolute right-4 top-8 bg-white border border-brand-border rounded-lg shadow-lg py-1 z-10 min-w-[160px]">
              {user.status === "INVITED" && (
                <button
                  onClick={() => {
                    onResendInvite(user);
                    setShowMenu(false);
                  }}
                  className="w-full px-4 py-2 text-left text-sm text-brand-ink hover:bg-gray-50 flex items-center gap-2"
                >
                  <RefreshCw className="w-4 h-4" />
                  Resend invite
                </button>
              )}
              {user.status === "ACTIVE" && (
                <button
                  onClick={() => {
                    onToggleStatus(user);
                    setShowMenu(false);
                  }}
                  className="w-full px-4 py-2 text-left text-sm text-brand-red hover:bg-gray-50 flex items-center gap-2"
                >
                  <UserX className="w-4 h-4" />
                  Deactivate
                </button>
              )}
              {user.status === "INACTIVE" && (
                <button
                  onClick={() => {
                    onToggleStatus(user);
                    setShowMenu(false);
                  }}
                  className="w-full px-4 py-2 text-left text-sm text-brand-green hover:bg-gray-50 flex items-center gap-2"
                >
                  <UserCheck className="w-4 h-4" />
                  Reactivate
                </button>
              )}
            </div>
          </>
        )}
      </td>
    </tr>
  );
}

export function UserManagement() {
  const { logout } = useAuth();
  const [activeTab, setActiveTab] = useState<RoleTab>("TEACHER");
  const [isModalOpen, setIsModalOpen] = useState(false);

  const { data: users, isLoading } = useSchoolUsers(activeTab);
  const inviteUser = useInviteUser();
  const updateUser = useUpdateUser();

  const handleInvite = async (data: {
    first_name: string;
    last_name: string;
    email: string;
    role: "TEACHER" | "STUDENT" | "PARENT";
  }) => {
    await inviteUser.mutateAsync(data);
  };

  const handleResendInvite = (_user: User) => {
    // TODO: Implement resend invite functionality
  };

  const handleToggleStatus = (user: User) => {
    const newStatus = user.status === "ACTIVE" ? "INACTIVE" : "ACTIVE";
    updateUser.mutate({ userId: user.id, status: newStatus });
  };

  const getTabHref = (tab: RoleTab) => {
    return `/school/users?role=${tab.toLowerCase()}`;
  };

  return (
    <DashboardLayout
      variant="school-admin"
      pageTitle="Users"
      pageSubtitle="Manage teachers, students, and parents at your school"
      onLogout={logout}
      topNavAction={
        <Button
          variant="primary"
          size="sm"
          onClick={() => setIsModalOpen(true)}
        >
          <Mail className="w-4 h-4 mr-1" />
          Invite user
        </Button>
      }
    >
      <div className="space-y-6">
        <div className="border-b border-brand-border">
          <nav className="flex gap-6" aria-label="User roles">
            {roleTabs.map((tab) => {
              const isActive = activeTab === tab.value;
              return (
                <Link
                  key={tab.value}
                  to={getTabHref(tab.value)}
                  onClick={(e) => {
                    e.preventDefault();
                    setActiveTab(tab.value);
                  }}
                  className={`py-3 px-1 text-sm font-medium border-b-2 transition-colors ${
                    isActive
                      ? "text-brand-primary border-brand-primary"
                      : "text-brand-muted border-transparent hover:text-brand-ink"
                  }`}
                  aria-current={isActive ? "page" : undefined}
                >
                  {tab.label}
                </Link>
              );
            })}
          </nav>
        </div>

        <Card
          variant="default"
          className="bg-white border-role-school-border overflow-hidden"
        >
          {isLoading ? (
            <div className="p-8 text-center text-brand-muted">Loading...</div>
          ) : users && users.length > 0 ? (
            <>
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="border-b border-brand-border text-left">
                      <th className="py-3 px-4 text-xs font-bold uppercase text-brand-muted">
                        Name
                      </th>
                      <th className="py-3 px-4 text-xs font-bold uppercase text-brand-muted">
                        Status
                      </th>
                      <th className="py-3 px-4 text-xs font-bold uppercase text-brand-muted w-12">
                        Actions
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {users.map((user) => (
                      <UserRow
                        key={user.id}
                        user={user}
                        onResendInvite={handleResendInvite}
                        onToggleStatus={handleToggleStatus}
                      />
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="p-4 border-t border-brand-border text-sm text-brand-muted">
                Showing {users.length} {activeTab.toLowerCase()}s
              </div>
            </>
          ) : (
            <div className="p-8 text-center text-brand-muted">
              No {activeTab.toLowerCase()}s found. Invite your first{" "}
              {activeTab.toLowerCase()} to get started.
            </div>
          )}
        </Card>

        <InviteUserModal
          isOpen={isModalOpen}
          onClose={() => setIsModalOpen(false)}
          onInvite={handleInvite}
          defaultRole={activeTab}
        />
      </div>
    </DashboardLayout>
  );
}
