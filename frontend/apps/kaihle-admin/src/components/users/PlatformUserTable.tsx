import { useState, useMemo } from "react";
import { LogIn } from "lucide-react";
import { Skeleton } from "@kaihle/ui";

export type UserRole =
  | "KAIHLE_ADMIN"
  | "SCHOOL_ADMIN"
  | "TEACHER"
  | "STUDENT"
  | "PARENT";

export interface PlatformUser {
  id: string;
  school_id: string | null;
  first_name: string;
  last_name: string;
  email: string;
  role: UserRole;
  is_active: boolean;
  last_active: string | null;
  school_name?: string;
}

interface PlatformUserTableProps {
  users: PlatformUser[];
  isLoading?: boolean;
  searchQuery: string;
  roleFilter: UserRole | "ALL";
  onSearchChange: (query: string) => void;
  onRoleFilterChange: (role: UserRole | "ALL") => void;
  onRowClick?: (user: PlatformUser) => void;
  /** Opens a session as this user in a new tab. */
  onImpersonate?: (user: PlatformUser) => void;
  /** Copies the impersonation link so it can be pasted into a private window. */
  onCopyImpersonateLink?: (user: PlatformUser) => void;
  /** id of the user whose link is currently being minted. */
  impersonatingUserId?: string | null;
  currentPage: number;
  totalPages: number;
  onPageChange: (page: number) => void;
}

/**
 * Mirrors the backend rule in AuthService.start_impersonation so the button is
 * never offered in a state that would come back 403.
 */
export function canImpersonate(user: PlatformUser): boolean {
  return user.is_active && user.role !== "KAIHLE_ADMIN";
}

function impersonateDisabledReason(user: PlatformUser): string {
  if (!user.is_active) return "Inactive users cannot be impersonated";
  return "Kaihle Admins cannot be impersonated";
}

const roleBadgeStyles: Record<UserRole, string> = {
  KAIHLE_ADMIN: "bg-purple-50 text-purple-700",
  SCHOOL_ADMIN: "bg-blue-50 text-blue-700",
  TEACHER: "bg-amber-50 text-amber-700",
  STUDENT: "bg-green-50 text-green-700",
  PARENT: "bg-pink-50 text-pink-600",
};

function getInitials(firstName: string, lastName: string): string {
  return `${firstName.charAt(0)}${lastName.charAt(0)}`.toUpperCase();
}

function formatDate(dateString: string | null): string {
  if (!dateString) return "—";
  const date = new Date(dateString);
  return date.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

export function PlatformUserTable({
  users,
  isLoading,
  searchQuery,
  roleFilter,
  onSearchChange,
  onRoleFilterChange,
  onRowClick,
  onImpersonate,
  onCopyImpersonateLink,
  impersonatingUserId,
  currentPage,
  totalPages,
  onPageChange,
}: PlatformUserTableProps) {
  const [localSearch, setLocalSearch] = useState(searchQuery);

  const handleSearchChange = (value: string) => {
    setLocalSearch(value);
    const timeoutId = setTimeout(() => {
      onSearchChange(value);
    }, 300);
    return () => clearTimeout(timeoutId);
  };

  const filteredUsers = useMemo(() => {
    return users;
  }, [users]);

  if (isLoading) {
    return (
      <div className="bg-white rounded-2xl border border-gray-200 overflow-hidden">
        <div className="p-4 border-b border-gray-200">
          <div className="flex gap-3">
            <Skeleton className="h-10 flex-1" />
            <Skeleton className="h-10 w-36" />
          </div>
        </div>
        <div className="divide-y divide-gray-50">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="px-4 py-4 flex items-center gap-4">
              <Skeleton className="w-8 h-8 rounded-full" />
              <Skeleton className="h-4 w-32" />
              <Skeleton className="h-4 w-24" />
              <Skeleton className="h-4 w-40" />
            </div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-2xl border border-gray-200 overflow-hidden">
      <div className="p-4 border-b border-gray-200">
        <div className="flex gap-3">
          <input
            type="text"
            placeholder="Search users..."
            value={localSearch}
            onChange={(e) => handleSearchChange(e.target.value)}
            className="flex-1 bg-white border border-gray-200 rounded-xl px-4 py-2 text-sm font-['Inter'] placeholder-gray-400 focus:border-brand-primary focus:ring-1 focus:ring-brand-primary/20 outline-none"
          />
          <select
            value={roleFilter}
            onChange={(e) =>
              onRoleFilterChange(e.target.value as UserRole | "ALL")
            }
            className="bg-white border border-gray-200 rounded-xl px-3 py-2 text-sm font-['Inter'] text-gray-600 focus:border-brand-primary focus:ring-1 focus:ring-brand-primary/20 outline-none"
          >
            <option value="ALL">All roles</option>
            <option value="KAIHLE_ADMIN">Kaihle Admin</option>
            <option value="SCHOOL_ADMIN">School Admin</option>
            <option value="TEACHER">Teacher</option>
            <option value="STUDENT">Student</option>
            <option value="PARENT">Parent</option>
          </select>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="bg-gray-50 border-b border-gray-200">
              <th className="text-left py-3 px-4 text-xs font-bold uppercase tracking-wide text-gray-400">
                Name
              </th>
              <th className="text-left py-3 px-4 text-xs font-bold uppercase tracking-wide text-gray-400">
                Role
              </th>
              <th className="text-left py-3 px-4 text-xs font-bold uppercase tracking-wide text-gray-400">
                School
              </th>
              <th className="text-left py-3 px-4 text-xs font-bold uppercase tracking-wide text-gray-400">
                Email
              </th>
              <th className="text-left py-3 px-4 text-xs font-bold uppercase tracking-wide text-gray-400">
                Status
              </th>
              <th className="text-left py-3 px-4 text-xs font-bold uppercase tracking-wide text-gray-400">
                Last active
              </th>
              <th className="text-left py-3 px-4 text-xs font-bold uppercase tracking-wide text-gray-400">
                Action
              </th>
            </tr>
          </thead>
          <tbody>
            {filteredUsers.length === 0 ? (
              <tr>
                <td colSpan={7} className="py-12 text-center text-gray-500">
                  <p className="font-['Inter'] text-sm">No users found</p>
                </td>
              </tr>
            ) : (
              filteredUsers.map((user) => (
                <tr
                  key={user.id}
                  onClick={() => onRowClick?.(user)}
                  className={`border-b border-gray-50 transition-colors ${
                    onRowClick ? "cursor-pointer hover:bg-gray-50" : ""
                  }`}
                >
                  <td className="py-3 px-4">
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-full bg-brand-light flex items-center justify-center text-brand-primary text-xs font-medium">
                        {getInitials(user.first_name, user.last_name)}
                      </div>
                      <span className="font-['Inter'] text-sm font-medium text-role-admin-ink">
                        {user.first_name} {user.last_name}
                      </span>
                    </div>
                  </td>
                  <td className="py-3 px-4">
                    <span
                      className={`rounded-full px-2.5 py-1 text-xs font-medium ${
                        roleBadgeStyles[user.role]
                      }`}
                    >
                      {user.role.replace("_", " ")}
                    </span>
                  </td>
                  <td className="py-3 px-4">
                    <span className="font-['Inter'] text-sm text-gray-600">
                      {user.school_name || "—"}
                    </span>
                  </td>
                  <td className="py-3 px-4">
                    <span className="font-['Inter'] text-sm text-gray-600">
                      {user.email}
                    </span>
                  </td>
                  <td className="py-3 px-4">
                    <span
                      className={`w-2 h-2 rounded-full inline-block mr-2 ${
                        user.is_active ? "bg-green-500" : "bg-gray-300"
                      }`}
                      aria-label={user.is_active ? "Active" : "Inactive"}
                    />
                    <span className="font-['Inter'] text-sm text-gray-600">
                      {user.is_active ? "Active" : "Inactive"}
                    </span>
                  </td>
                  <td className="py-3 px-4">
                    <span className="font-['Inter'] text-sm text-gray-600">
                      {formatDate(user.last_active)}
                    </span>
                  </td>
                  <td className="py-3 px-4">
                    <div className="flex items-center gap-3">
                      {onImpersonate && (
                        <button
                          type="button"
                          // The row opens the edit drawer — without this the
                          // drawer would fly open behind the new tab.
                          onClick={(e) => {
                            e.stopPropagation();
                            onImpersonate(user);
                          }}
                          // Disabled while ANY row is minting, not just this one.
                          // Two impersonations of the same role land on the same
                          // origin and share its localStorage, so the second
                          // would silently replace the first.
                          disabled={
                            !canImpersonate(user) ||
                            Boolean(impersonatingUserId)
                          }
                          title={
                            !canImpersonate(user)
                              ? impersonateDisabledReason(user)
                              : Boolean(impersonatingUserId)
                                ? "Another session is being opened"
                                : `Open a session as ${user.first_name}`
                          }
                          className="inline-flex items-center gap-1.5 rounded-lg border border-gray-200 px-2.5 py-1.5 font-['Inter'] text-sm font-medium text-brand-primary transition-colors hover:bg-gray-50 disabled:cursor-not-allowed disabled:text-gray-400 disabled:hover:bg-transparent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2 min-h-[36px]"
                        >
                          {impersonatingUserId === user.id ? (
                            <span
                              className="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent"
                              aria-hidden="true"
                            />
                          ) : (
                            <LogIn className="h-4 w-4" aria-hidden="true" />
                          )}
                          Log in as
                        </button>
                      )}
                      {onCopyImpersonateLink && canImpersonate(user) && (
                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation();
                            onCopyImpersonateLink(user);
                          }}
                          disabled={Boolean(impersonatingUserId)}
                          title="Copy a link to paste into a private window"
                          className="font-['Inter'] text-sm text-gray-500 underline-offset-2 transition-colors hover:text-brand-primary hover:underline disabled:cursor-not-allowed disabled:text-gray-300 disabled:no-underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2"
                        >
                          Copy link
                        </button>
                      )}
                      {onRowClick && (
                        <span className="font-['Inter'] text-sm font-medium text-brand-primary">
                          Edit →
                        </span>
                      )}
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {totalPages > 1 && (
        <div className="px-4 py-3 border-t border-gray-200 flex items-center justify-between">
          <span className="font-['Inter'] text-sm text-gray-600">
            Page {currentPage} of {totalPages}
          </span>
          <div className="flex gap-2">
            <button
              onClick={() => onPageChange(currentPage - 1)}
              disabled={currentPage === 1}
              className="px-3 py-1.5 border border-gray-200 rounded-lg text-sm font-['Inter'] text-gray-600 hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed min-h-[36px]"
            >
              Previous
            </button>
            <button
              onClick={() => onPageChange(currentPage + 1)}
              disabled={currentPage === totalPages}
              className="px-3 py-1.5 border border-gray-200 rounded-lg text-sm font-['Inter'] text-gray-600 hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed min-h-[36px]"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
