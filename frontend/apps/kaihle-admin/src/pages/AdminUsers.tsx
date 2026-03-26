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
import { DeactivateUserModal } from "../components/users/DeactivateUserModal";

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
  const [selectedUser, setSelectedUser] = useState<PlatformUser | null>(null);

  const pageSize = 25;

  const { data, isLoading } = usePlatformUsers({
    q: searchQuery,
    role: roleFilter,
    page: currentPage,
    page_size: pageSize,
  });

  const deactivateMutation = useDeactivateUser();

  const users = data?.users ?? [];
  const totalUsers = data?.total ?? 0;
  const totalPages = Math.ceil(totalUsers / pageSize);

  const handleDeactivateClick = (user: PlatformUser) => {
    setSelectedUser(user);
  };

  const handleDeactivateClose = () => {
    setSelectedUser(null);
  };

  const handleDeactivateConfirm = async () => {
    if (!selectedUser) return;

    const schoolId = selectedUser.school_id || "platform";
    await deactivateMutation.mutateAsync({
      schoolId,
      userId: selectedUser.id,
    });
    setSelectedUser(null);
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
        onDeactivateClick={handleDeactivateClick}
        currentPage={currentPage}
        totalPages={totalPages}
        onPageChange={setCurrentPage}
      />

      <DeactivateUserModal
        isOpen={!!selectedUser}
        onClose={handleDeactivateClose}
        onConfirm={handleDeactivateConfirm}
        userName={
          selectedUser
            ? `${selectedUser.first_name} ${selectedUser.last_name}`
            : ""
        }
        userEmail={selectedUser?.email ?? ""}
        isLoading={deactivateMutation.isPending}
      />
    </AdminLayout>
  );
}
