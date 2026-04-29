import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@kaihle/auth";
import { AdminLayout } from "@kaihle/ui";
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
