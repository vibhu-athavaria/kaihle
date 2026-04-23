import { useState, useMemo } from "react";
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
  onDeactivateClick: (user: PlatformUser) => void;
  currentPage: number;
  totalPages: number;
  onPageChange: (page: number) => void;
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
  onDeactivateClick,
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
                  className="border-b border-gray-50 hover:bg-gray-50 transition-colors"
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
                    {user.is_active && (
                      <button
                        onClick={() => onDeactivateClick(user)}
                        className="text-red-500 text-xs hover:text-red-700 font-['Inter'] min-h-[44px] px-2 focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2 rounded"
                      >
                        Deactivate
                      </button>
                    )}
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
