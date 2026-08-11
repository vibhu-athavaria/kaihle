import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@kaihle/auth";
import { AdminLayout, toast } from "@kaihle/ui";
import { useAuth } from "@kaihle/auth";
import {
  PlatformUserTable,
  UserRole,
  PlatformUser,
} from "../components/users/PlatformUserTable";
import { EditUserDrawer } from "../components/users/EditUserDrawer";

interface PlatformUsersResponse {
  users: PlatformUser[];
  total: number;
  page: number;
  page_size: number;
}

function usePlatformUsers(params: {
  q?: string;
  role?: UserRole | "ALL";
  page?: number;
  page_size?: number;
}) {
  return useQuery({
    queryKey: ["platform", "users", params],
    queryFn: async () => {
      const response = await apiClient.get("/api/v1/platform/users", {
        params,
      });
      return response.data as PlatformUsersResponse;
    },
  });
}

interface ImpersonationStartResponse {
  redirect_url: string;
  target_app_url: string;
  target_user_id: string;
  target_role: string;
  expires_in_seconds: number;
}

/**
 * Mints a single-use link that opens a session as the given user.
 *
 * Not a React Query `useQuery` — this has a side effect (it burns a token) and
 * must never be cached, refetched, or deduped.
 */
function useImpersonateUser() {
  return useMutation({
    mutationFn: async (userId: string) => {
      const response = await apiClient.post(
        `/api/v1/platform/users/${userId}/impersonate`,
      );
      return response.data as ImpersonationStartResponse;
    },
  });
}

function useUpdateUser() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (payload: {
      userId: string;
      schoolId: string;
      firstName: string;
      lastName: string;
      role: UserRole;
      password?: string;
    }) => {
      const data: Record<string, string> = {
        first_name: payload.firstName,
        last_name: payload.lastName,
        role: payload.role,
      };
      if (payload.password) {
        data.password = payload.password;
      }
      const response = await apiClient.patch(
        `/api/v1/schools/${payload.schoolId}/users/${payload.userId}`,
        data,
      );
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["platform", "users"] });
    },
  });
}

function useDeactivateUser() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (payload: { schoolId: string; userId: string }) => {
      const response = await apiClient.delete(
        `/api/v1/schools/${payload.schoolId}/users/${payload.userId}`,
      );
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["platform", "users"] });
    },
  });
}

export function AdminUsers() {
  const { logout } = useAuth();
  const [searchQuery, setSearchQuery] = useState("");
  const [roleFilter, setRoleFilter] = useState<UserRole | "ALL">("ALL");
  const [currentPage, setCurrentPage] = useState(1);
  const [editingUser, setEditingUser] = useState<PlatformUser | null>(null);

  const pageSize = 25;

  const { data, isLoading } = usePlatformUsers({
    q: searchQuery,
    role: roleFilter,
    page: currentPage,
    page_size: pageSize,
  });

  const updateMutation = useUpdateUser();
  const deactivateMutation = useDeactivateUser();
  const impersonateMutation = useImpersonateUser();
  const [impersonatingUserId, setImpersonatingUserId] = useState<string | null>(
    null,
  );

  const users = data?.users ?? [];
  const totalUsers = data?.total ?? 0;
  const totalPages = Math.ceil(totalUsers / pageSize);

  const handleRowClick = (user: PlatformUser) => {
    setEditingUser(user);
  };

  const handleCloseDrawer = () => {
    setEditingUser(null);
  };

  const handleSave = async (data: {
    userId: string;
    schoolId: string;
    firstName: string;
    lastName: string;
    role: UserRole;
    password?: string;
  }) => {
    await updateMutation.mutateAsync(data);
    setEditingUser(null);
  };

  const startImpersonation = async (
    user: PlatformUser,
  ): Promise<ImpersonationStartResponse | null> => {
    setImpersonatingUserId(user.id);
    try {
      return await impersonateMutation.mutateAsync(user.id);
    } catch (err) {
      // Surface the server's reason ("Cannot impersonate an inactive user",
      // etc.) rather than a generic failure — a silent no-op here is
      // indistinguishable from a broken button.
      const detail = (err as { response?: { data?: { detail?: string } } })
        ?.response?.data?.detail;
      toast.error(detail ?? `Could not start a session as ${user.first_name}.`);
      return null;
    } finally {
      setImpersonatingUserId(null);
    }
  };

  const handleImpersonate = async (user: PlatformUser) => {
    // The tab MUST be opened synchronously, inside the click's user-activation
    // window. Opening it after `await` looks like an unsolicited popup to Chrome
    // and Safari, which block it silently — the button appears to do nothing.
    // So: claim the tab now, fill in its URL once the token arrives.
    const tab = window.open("", "_blank");

    if (!tab) {
      toast.error(
        "Your browser blocked the new tab. Allow pop-ups for this site, or use Copy link.",
      );
      return;
    }
    // Can't pass "noopener" to window.open above — it makes the call return null,
    // leaving no handle to navigate. Sever the back-reference manually instead.
    tab.opener = null;

    const result = await startImpersonation(user);
    if (!result) {
      tab.close();
      return;
    }
    tab.location.replace(result.redirect_url);
  };

  const handleCopyImpersonateLink = async (user: PlatformUser) => {
    const result = await startImpersonation(user);
    if (!result) return;
    try {
      await navigator.clipboard.writeText(result.redirect_url);
      toast.success(
        `Link copied — paste it into a private window within ${result.expires_in_seconds}s.`,
      );
    } catch {
      toast.error("Could not copy the link to your clipboard.");
    }
  };

  const handleDeactivate = async (userId: string, schoolId: string) => {
    await deactivateMutation.mutateAsync({ userId, schoolId });
    setEditingUser(null);
  };

  return (
    <AdminLayout pageTitle="Platform users" onLogout={logout}>
      <PlatformUserTable
        users={users}
        isLoading={isLoading}
        searchQuery={searchQuery}
        roleFilter={roleFilter}
        onSearchChange={setSearchQuery}
        onRoleFilterChange={(role) => {
          setRoleFilter(role);
          setCurrentPage(1);
        }}
        onRowClick={handleRowClick}
        onImpersonate={handleImpersonate}
        onCopyImpersonateLink={handleCopyImpersonateLink}
        impersonatingUserId={impersonatingUserId}
        currentPage={currentPage}
        totalPages={totalPages}
        onPageChange={setCurrentPage}
      />

      <EditUserDrawer
        user={editingUser}
        isOpen={!!editingUser}
        onClose={handleCloseDrawer}
        onSave={handleSave}
        onDeactivate={handleDeactivate}
        isSaving={updateMutation.isPending}
        isDeactivating={deactivateMutation.isPending}
      />
    </AdminLayout>
  );
}
