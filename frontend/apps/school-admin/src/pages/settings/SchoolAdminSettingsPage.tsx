import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@kaihle/auth";
import { useAuth } from "@kaihle/auth";
import { UserRole } from "@kaihle/types";
import { DashboardLayout } from "@kaihle/ui";
import { Info } from "lucide-react";

interface User {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  role: UserRole;
  school_id: string;
}

interface School {
  id: string;
  name: string;
  country: string;
  city: string;
  timezone: string;
  slug: string;
}

function MyAccountSection({
  user,
  onNameUpdated,
}: {
  user: User | undefined;
  onNameUpdated: () => void;
}) {
  const queryClient = useQueryClient();
  const [editingName, setEditingName] = useState(false);
  const [editingPassword, setEditingPassword] = useState(false);
  const [firstName, setFirstName] = useState(user?.first_name || "");
  const [lastName, setLastName] = useState(user?.last_name || "");
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [passwordError, setPasswordError] = useState<string | null>(null);
  const [nameError, setNameError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const updateNameMutation = useMutation({
    mutationFn: async (data: { first_name: string; last_name: string }) => {
      await apiClient.patch("/api/v1/users/me", data);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["school-admin", "settings", "user"],
      });
      setEditingName(false);
      onNameUpdated();
    },
    onError: () => {
      setNameError("Failed to update name");
    },
  });

  const changePasswordMutation = useMutation({
    mutationFn: async (data: {
      current_password: string;
      new_password: string;
      confirm_password: string;
    }) => {
      await apiClient.post("/api/v1/auth/change-password", data);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["school-admin", "settings", "user"],
      });
      setEditingPassword(false);
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
      setPasswordError(null);
    },
    onError: (error: unknown) => {
      if (
        typeof error === "object" &&
        error !== null &&
        "isAxiosError" in error
      ) {
        const axiosError = error as {
          isAxiosError: boolean;
          response?: { status?: number };
        };
        if (axiosError.response?.status === 400) {
          setPasswordError("Current password is incorrect");
        } else {
          setPasswordError("Failed to change password");
        }
      } else {
        setPasswordError("Failed to change password");
      }
    },
  });

  const handleSaveName = () => {
    if (!firstName.trim() || !lastName.trim()) {
      setNameError("First name and last name are required");
      return;
    }
    updateNameMutation.mutate({ first_name: firstName, last_name: lastName });
  };

  const handleCancelName = () => {
    setEditingName(false);
    setFirstName(user?.first_name || "");
    setLastName(user?.last_name || "");
    setNameError(null);
  };

  const handleCancelPassword = () => {
    setEditingPassword(false);
    setCurrentPassword("");
    setNewPassword("");
    setConfirmPassword("");
    setPasswordError(null);
  };

  const handlePasswordMismatch = () => {
    if (newPassword !== confirmPassword) {
      setPasswordError("Passwords do not match");
      return true;
    }
    setPasswordError(null);
    return false;
  };

  const handleSubmitPassword = (e: React.FormEvent) => {
    e.preventDefault();
    if (newPassword.length < 8) {
      setPasswordError("Password must be at least 8 characters");
      return;
    }
    if (handlePasswordMismatch()) {
      return;
    }
    changePasswordMutation.mutate({
      current_password: currentPassword,
      new_password: newPassword,
      confirm_password: confirmPassword,
    });
  };

  const displayName = user ? `${user.first_name} ${user.last_name}` : "—";

  return (
    <div className="bg-white border border-role-school-border rounded-2xl">
      <h2 className="font-display text-base text-brand-ink px-6 pt-5 pb-3 border-b border-role-school-border">
        MY ACCOUNT
      </h2>

      {/* Name row */}
      <div className="px-6 py-4 flex items-center justify-between">
        <div>
          <div className="font-sans text-sm font-medium text-brand-ink">
            Name
          </div>
          <div className="font-sans text-sm text-role-school-muted">
            {displayName}
          </div>
        </div>
        {!editingName && (
          <button
            type="button"
            onClick={() => {
              setEditingPassword(false);
              setEditingName(true);
            }}
            className="text-brand-primary text-sm font-medium cursor-pointer focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2 rounded min-h-[44px] px-2"
          >
            Edit
          </button>
        )}
      </div>

      {editingName && (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleSaveName();
          }}
          className="px-6 pb-4 pt-1 bg-brand-light/30 border-b border-role-school-border"
        >
          <div className="flex gap-3 mb-3">
            <div className="flex-1">
              <label
                htmlFor="firstName"
                className="block font-sans text-xs font-medium text-brand-ink mb-1"
              >
                First name
              </label>
              <input
                id="firstName"
                type="text"
                value={firstName}
                onChange={(e) => setFirstName(e.target.value)}
                className="w-full rounded-lg border border-role-school-border px-3 py-2 text-sm font-sans text-brand-ink focus:border-brand-primary focus:ring-1 focus:ring-brand-primary/20 outline-none"
              />
            </div>
            <div className="flex-1">
              <label
                htmlFor="lastName"
                className="block font-sans text-xs font-medium text-brand-ink mb-1"
              >
                Last name
              </label>
              <input
                id="lastName"
                type="text"
                value={lastName}
                onChange={(e) => setLastName(e.target.value)}
                className="w-full rounded-lg border border-role-school-border px-3 py-2 text-sm font-sans text-brand-ink focus:border-brand-primary focus:ring-1 focus:ring-brand-primary/20 outline-none"
              />
            </div>
          </div>
          {nameError && (
            <div className="text-red-500 text-xs mb-3">{nameError}</div>
          )}
          <div className="flex gap-2">
            <button
              type="submit"
              disabled={updateNameMutation.isPending}
              className="bg-brand-primary text-white rounded-full px-4 py-2 text-sm font-medium min-h-[44px] focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2 disabled:opacity-60"
            >
              {updateNameMutation.isPending ? "Saving..." : "Save"}
            </button>
            <button
              type="button"
              onClick={handleCancelName}
              disabled={updateNameMutation.isPending}
              className="border border-role-school-border text-brand-ink rounded-full px-4 py-2 text-sm font-medium min-h-[44px] focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2 disabled:opacity-60"
            >
              Cancel
            </button>
          </div>
        </form>
      )}

      <div className="h-px bg-role-school-border mx-6" />

      {/* Email row */}
      <div className="px-6 py-4 flex items-center justify-between">
        <div>
          <div className="font-sans text-sm font-medium text-brand-ink">
            Email
          </div>
          <div className="font-sans text-sm text-role-school-muted">
            {user?.email || "—"}
          </div>
        </div>
        <span className="bg-brand-light text-role-school-muted text-xs rounded-full px-2 py-0.5">
          Managed by school
        </span>
      </div>

      <div className="h-px bg-role-school-border mx-6" />

      {/* Password row */}
      <div className="px-6 py-4 flex items-center justify-between">
        <div>
          <div className="font-sans text-sm font-medium text-brand-ink">
            Password
          </div>
          <div className="font-sans text-sm text-role-school-muted">
            Last changed —
          </div>
        </div>
        {!editingPassword && (
          <button
            type="button"
            onClick={() => {
              setEditingName(false);
              setEditingPassword(true);
            }}
            className="text-brand-primary text-sm font-medium cursor-pointer focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2 rounded min-h-[44px] px-2"
          >
            Change
          </button>
        )}
      </div>

      {editingPassword && (
        <form
          onSubmit={handleSubmitPassword}
          className="px-6 pb-4 pt-1 bg-brand-light/30 border-b border-role-school-border"
        >
          <div className="space-y-3 mb-3">
            <div>
              <label
                htmlFor="currentPassword"
                className="block font-sans text-xs font-medium text-brand-ink mb-1"
              >
                Current password
              </label>
              <input
                id="currentPassword"
                type="password"
                value={currentPassword}
                onChange={(e) => setCurrentPassword(e.target.value)}
                placeholder="Enter current password"
                className="w-full rounded-lg border border-role-school-border px-3 py-2 text-sm font-sans text-brand-ink focus:border-brand-primary focus:ring-1 focus:ring-brand-primary/20 outline-none"
                disabled={isLoading}
              />
            </div>
            <div>
              <label
                htmlFor="newPassword"
                className="block font-sans text-xs font-medium text-brand-ink mb-1"
              >
                New password
              </label>
              <input
                id="newPassword"
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                placeholder="Enter new password"
                className="w-full rounded-lg border border-role-school-border px-3 py-2 text-sm font-sans text-brand-ink focus:border-brand-primary focus:ring-1 focus:ring-brand-primary/20 outline-none"
                disabled={isLoading}
              />
            </div>
            <div>
              <label
                htmlFor="confirmPassword"
                className="block font-sans text-xs font-medium text-brand-ink mb-1"
              >
                Confirm new password
              </label>
              <input
                id="confirmPassword"
                type="password"
                value={confirmPassword}
                onChange={(e) => {
                  setConfirmPassword(e.target.value);
                  if (e.target.value !== newPassword) {
                    setPasswordError("Passwords do not match");
                  } else {
                    setPasswordError(null);
                  }
                }}
                placeholder="Confirm new password"
                className="w-full rounded-lg border border-role-school-border px-3 py-2 text-sm font-sans text-brand-ink focus:border-brand-primary focus:ring-1 focus:ring-brand-primary/20 outline-none"
                disabled={isLoading}
              />
            </div>
          </div>
          {passwordError && (
            <div className="text-red-500 text-xs mb-3">{passwordError}</div>
          )}
          <div className="flex gap-2">
            <button
              type="submit"
              disabled={
                isLoading ||
                !!passwordError ||
                !currentPassword ||
                !newPassword ||
                !confirmPassword
              }
              className="bg-brand-primary text-white rounded-full px-4 py-2 text-sm font-medium min-h-[44px] focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2 disabled:opacity-60 disabled:cursor-not-allowed"
            >
              Update password
            </button>
            <button
              type="button"
              onClick={handleCancelPassword}
              disabled={isLoading}
              className="border border-role-school-border text-brand-ink rounded-full px-4 py-2 text-sm font-medium min-h-[44px] focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2 disabled:opacity-60"
            >
              Cancel
            </button>
          </div>
        </form>
      )}
    </div>
  );
}

function SchoolProfileSection({ school }: { school: School | undefined }) {
  if (!school) {
    return (
      <div className="bg-white border border-role-school-border rounded-2xl p-5">
        <h2 className="font-display text-base text-brand-ink pb-3 border-b border-role-school-border">
          SCHOOL PROFILE
        </h2>
        <div className="animate-pulse space-y-3 mt-4">
          <div className="h-4 bg-brand-border rounded-full w-3/4" />
          <div className="h-4 bg-brand-border rounded-full w-1/2" />
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white border border-role-school-border rounded-2xl p-5">
      <h2 className="font-display text-base text-brand-ink pb-3 border-b border-role-school-border">
        SCHOOL PROFILE
      </h2>

      <div className="space-y-3 mt-4">
        <div className="flex justify-between">
          <span className="font-sans text-sm text-role-school-muted">
            School name
          </span>
          <span className="font-sans text-sm text-brand-ink">
            {school.name}
          </span>
        </div>
        <div className="flex justify-between">
          <span className="font-sans text-sm text-role-school-muted">
            Country
          </span>
          <span className="font-sans text-sm text-brand-ink">
            {school.country}
          </span>
        </div>
        <div className="flex justify-between">
          <span className="font-sans text-sm text-role-school-muted">City</span>
          <span className="font-sans text-sm text-brand-ink">
            {school.city}
          </span>
        </div>
        <div className="flex justify-between">
          <span className="font-sans text-sm text-role-school-muted">
            Timezone
          </span>
          <span className="font-sans text-sm text-brand-ink">
            {school.timezone}
          </span>
        </div>
        <div className="flex justify-between">
          <span className="font-sans text-sm text-role-school-muted">
            School slug
          </span>
          <span className="font-mono text-sm text-gray-600">{school.slug}</span>
        </div>
      </div>

      <div className="mt-4 bg-blue-50 border border-blue-100 rounded-lg p-3 flex gap-2">
        <Info
          className="w-4 h-4 text-blue-500 flex-shrink-0 mt-0.5"
          aria-hidden="true"
        />
        <p className="font-sans text-xs text-blue-700">
          School profile is managed by Kaihle. Contact support@kaihle.com to
          request changes.
        </p>
      </div>
    </div>
  );
}

function AccountActionsSection({ onLogout }: { onLogout: () => void }) {
  const { logout } = useAuth();
  const [isLoading, setIsLoading] = useState(false);

  const handleSignOut = async () => {
    setIsLoading(true);
    try {
      await apiClient.post("/api/v1/auth/logout");
    } finally {
      logout();
    }
  };

  return (
    <div className="bg-white border border-red-200 rounded-2xl">
      <h2 className="font-display text-base text-brand-ink px-6 pt-5 pb-3 border-b border-role-school-border">
        ACCOUNT ACTIONS
      </h2>

      <div className="px-6 py-5">
        <button
          type="button"
          onClick={handleSignOut}
          disabled={isLoading}
          className="border border-red-200 text-red-600 rounded-full px-4 py-2 text-sm font-medium w-full hover:bg-red-50 transition-colors min-h-[44px] disabled:opacity-60 disabled:cursor-not-allowed focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2"
        >
          {isLoading ? (
            <span className="flex items-center justify-center gap-2">
              <span className="animate-spin rounded-full h-4 w-4 border-b-2 border-red-600" />
              Signing out...
            </span>
          ) : (
            "Sign out"
          )}
        </button>
        <p className="font-sans text-xs text-role-school-muted mt-2 text-center">
          You will need to sign in again.
        </p>
      </div>
    </div>
  );
}

export function SchoolAdminSettingsPage() {
  const { user, logout } = useAuth();

  const { data: userData } = useQuery<User>({
    queryKey: ["school-admin", "settings", "user"],
    queryFn: async () => {
      const response = await apiClient.get<User>("/api/v1/users/me");
      return response.data;
    },
  });

  const { data: schoolData } = useQuery<School>({
    queryKey: ["school-admin", "settings", "school"],
    queryFn: async () => {
      const schoolId = userData?.school_id;
      if (!schoolId) throw new Error("No school_id");
      const response = await apiClient.get<School>(
        `/api/v1/schools/${schoolId}`,
      );
      return response.data;
    },
    enabled: !!userData?.school_id,
  });

  const displayName = userData
    ? `${userData.first_name} ${userData.last_name}`
    : "School Admin";
  const schoolName = schoolData?.name || "School";

  return (
    <DashboardLayout
      variant="school-admin"
      pageTitle="Settings"
      onLogout={logout}
    >
      <div className="max-w-lg mx-auto px-4 py-6">
        <div className="mb-6">
          <h1 className="font-display text-2xl text-brand-ink">Settings</h1>
          <p className="font-sans text-sm text-role-school-muted mt-1">
            {displayName} · School Admin · {schoolName}
          </p>
        </div>

        <div className="space-y-4">
          <MyAccountSection user={userData} onNameUpdated={() => {}} />
          <SchoolProfileSection school={schoolData} />
          <AccountActionsSection onLogout={logout} />
        </div>
      </div>
    </DashboardLayout>
  );
}
