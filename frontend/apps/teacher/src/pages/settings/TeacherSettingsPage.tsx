import { useState, useCallback, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth, apiClient, useAuthStore } from "@kaihle/auth";
import { Button, toast } from "@kaihle/ui";

interface UserProfile {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  role: string;
  school_id: string | null;
  updated_at?: string;
}

function formatRelativeTime(dateString: string | undefined): string {
  if (!dateString) return "—";
  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMonths = Math.floor(diffMs / (1000 * 60 * 60 * 24 * 30));
  if (diffMonths < 1) return "Less than a month ago";
  if (diffMonths === 1) return "1 month ago";
  if (diffMonths < 12) return `${diffMonths} months ago`;
  const diffYears = Math.floor(diffMonths / 12);
  if (diffYears === 1) return "1 year ago";
  return `${diffYears} years ago`;
}

async function fetchUserProfile(schoolId: string): Promise<UserProfile> {
  const response = await apiClient.get<UserProfile>(
    `/api/v1/schools/${schoolId}/users/me`,
  );
  return response.data;
}

export function TeacherSettingsPage() {
  const { user: authUser, logout } = useAuth();
  const navigate = useNavigate();
  const [editingName, setEditingName] = useState(false);
  const [editingPassword, setEditingPassword] = useState(false);
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [nameError, setNameError] = useState<string | null>(null);
  const [passwordError, setPasswordError] = useState<string | null>(null);
  const [isLoadingName, setIsLoadingName] = useState(false);
  const [isLoadingPassword, setIsLoadingPassword] = useState(false);

  useEffect(() => {
    const schoolId = useAuthStore.getState().user?.school_id;
    if (!schoolId) {
      return;
    }
    fetchUserProfile(schoolId)
      .then((data) => {
        setProfile(data);
        setFirstName(data.first_name || "");
        setLastName(data.last_name || "");
      })
      .catch(() => {
        // Use auth user data as fallback
        setFirstName("");
        setLastName("");
      });
  }, []);

  const displayName = profile
    ? `${profile.first_name || ""} ${profile.last_name || ""}`.trim() ||
      profile.email?.split("@")[0] ||
      "Teacher"
    : authUser?.email?.split("@")[0] || "Teacher";

  const handleEditName = useCallback(() => {
    setEditingName(true);
    setEditingPassword(false);
    setNameError(null);
  }, []);

  const handleEditPassword = useCallback(() => {
    setEditingPassword(true);
    setEditingName(false);
    setCurrentPassword("");
    setNewPassword("");
    setConfirmPassword("");
    setPasswordError(null);
  }, []);

  const handleCancelName = useCallback(() => {
    setEditingName(false);
    if (profile) {
      setFirstName(profile.first_name || "");
      setLastName(profile.last_name || "");
    }
    setNameError(null);
  }, [profile]);

  const handleCancelPassword = useCallback(() => {
    setEditingPassword(false);
    setCurrentPassword("");
    setNewPassword("");
    setConfirmPassword("");
    setPasswordError(null);
  }, []);

  const handleSaveName = useCallback(async () => {
    if (!firstName.trim() || !lastName.trim()) {
      setNameError("Both first and last name are required");
      return;
    }
    const schoolId = useAuthStore.getState().user?.school_id;
    if (!schoolId) {
      setNameError("No school_id found for current user");
      return;
    }
    setIsLoadingName(true);
    setNameError(null);
    try {
      const response = await apiClient.patch<UserProfile>(
        `/api/v1/schools/${schoolId}/users/me`,
        {
          first_name: firstName.trim(),
          last_name: lastName.trim(),
        },
      );
      setProfile(response.data);
      toast.success("Name updated");
      setEditingName(false);
    } catch {
      setNameError("Failed to update name. Please try again.");
    } finally {
      setIsLoadingName(false);
    }
  }, [firstName, lastName]);

  const handleSavePassword = useCallback(async () => {
    setPasswordError(null);
    if (!currentPassword) {
      setPasswordError("Current password is required");
      return;
    }
    if (newPassword.length < 8) {
      setPasswordError("New password must be at least 8 characters");
      return;
    }
    if (newPassword !== confirmPassword) {
      setPasswordError("New passwords do not match");
      return;
    }
    setIsLoadingPassword(true);
    try {
      await apiClient.post("/api/v1/auth/change-password", {
        current_password: currentPassword,
        new_password: newPassword,
      });
      toast.success("Password updated");
      setEditingPassword(false);
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
    } catch (error: unknown) {
      const err = error as { response?: { status?: number } };
      if (err.response?.status === 400) {
        setPasswordError("Current password is incorrect");
      } else {
        setPasswordError("Failed to update password. Please try again.");
      }
    } finally {
      setIsLoadingPassword(false);
    }
  }, [currentPassword, newPassword, confirmPassword]);

  const handleSignOut = useCallback(async () => {
    try {
      await apiClient.post("/api/v1/auth/logout", {});
    } catch {
      // Ignore logout errors
    }
    await logout();
    navigate("/login");
  }, [logout, navigate]);

  const passwordMismatch =
    newPassword && confirmPassword && newPassword !== confirmPassword;

  const canSubmitPassword =
    currentPassword && newPassword.length >= 8 && passwordMismatch === false;

  return (
    <div className="p-6 max-w-lg">
      <h1 className="font-display font-bold text-2xl text-brand-ink mb-6">
        Settings
      </h1>

      {/* Account Section */}
      <div className="mb-8">
        <h2 className="font-sans text-xs font-bold uppercase tracking-widest text-role-teacher-muted mb-4">
          Account
        </h2>
        <div className="bg-white border border-role-teacher-border rounded-2xl divide-y divide-gray-100">
          {/* Name Row */}
          <div className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="font-semibold text-sm text-brand-ink">Name</p>
                <p className="text-sm text-role-teacher-body">{displayName}</p>
              </div>
              {!editingName && (
                <button
                  onClick={handleEditName}
                  className="text-brand-gold hover:text-amber-600 text-sm font-medium focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2 rounded min-h-[44px] px-3"
                >
                  Edit
                </button>
              )}
            </div>
            {editingName && (
              <div className="mt-4 space-y-3">
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label
                      htmlFor="firstName"
                      className="block text-xs font-medium text-role-teacher-body mb-1"
                    >
                      First name
                    </label>
                    <input
                      id="firstName"
                      type="text"
                      value={firstName}
                      onChange={(e) => setFirstName(e.target.value)}
                      className="w-full px-3 py-2 border border-brand-border rounded-lg text-sm text-brand-ink focus:outline-none focus:ring-2 focus:ring-brand-primary focus:border-transparent"
                    />
                  </div>
                  <div>
                    <label
                      htmlFor="lastName"
                      className="block text-xs font-medium text-role-teacher-body mb-1"
                    >
                      Last name
                    </label>
                    <input
                      id="lastName"
                      type="text"
                      value={lastName}
                      onChange={(e) => setLastName(e.target.value)}
                      className="w-full px-3 py-2 border border-brand-border rounded-lg text-sm text-brand-ink focus:outline-none focus:ring-2 focus:ring-brand-primary focus:border-transparent"
                    />
                  </div>
                </div>
                {nameError && (
                  <p className="text-sm text-red-600">{nameError}</p>
                )}
                <div className="flex gap-2">
                  <Button
                    onClick={handleSaveName}
                    disabled={isLoadingName}
                    className="bg-brand-gold hover:bg-brand-gold-dark text-white min-h-[44px]"
                    size="sm"
                  >
                    {isLoadingName ? "Saving..." : "Save"}
                  </Button>
                  <Button
                    onClick={handleCancelName}
                    disabled={isLoadingName}
                    variant="secondary"
                    className="border border-brand-border text-brand-ink hover:bg-gray-50 min-h-[44px]"
                    size="sm"
                  >
                    Cancel
                  </Button>
                </div>
              </div>
            )}
          </div>

          {/* Email Row */}
          <div className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="font-semibold text-sm text-brand-ink">Email</p>
                <p className="text-sm text-role-teacher-body">
                  {profile?.email || authUser?.email}
                </p>
              </div>
              <span className="text-xs text-role-teacher-muted">
                Managed by school
              </span>
            </div>
          </div>

          {/* Password Row */}
          <div className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="font-semibold text-sm text-brand-ink">Password</p>
                <p className="text-sm text-role-teacher-body">
                  Last changed {formatRelativeTime(profile?.updated_at)}
                </p>
              </div>
              {!editingPassword && (
                <button
                  onClick={handleEditPassword}
                  className="text-brand-gold hover:text-amber-600 text-sm font-medium focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2 rounded min-h-[44px] px-3"
                >
                  Change
                </button>
              )}
            </div>
            {editingPassword && (
              <div className="mt-4 space-y-3">
                <div>
                  <label
                    htmlFor="currentPassword"
                    className="block text-xs font-medium text-role-teacher-body mb-1"
                  >
                    Current password
                  </label>
                  <input
                    id="currentPassword"
                    type="password"
                    value={currentPassword}
                    onChange={(e) => setCurrentPassword(e.target.value)}
                    className="w-full px-3 py-2 border border-brand-border rounded-lg text-sm text-brand-ink focus:outline-none focus:ring-2 focus:ring-brand-primary focus:border-transparent"
                  />
                </div>
                <div>
                  <label
                    htmlFor="newPassword"
                    className="block text-xs font-medium text-role-teacher-body mb-1"
                  >
                    New password
                  </label>
                  <input
                    id="newPassword"
                    type="password"
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
                    className="w-full px-3 py-2 border border-brand-border rounded-lg text-sm text-brand-ink focus:outline-none focus:ring-2 focus:ring-brand-primary focus:border-transparent"
                  />
                </div>
                <div>
                  <label
                    htmlFor="confirmPassword"
                    className="block text-xs font-medium text-role-teacher-body mb-1"
                  >
                    Confirm new password
                  </label>
                  <input
                    id="confirmPassword"
                    type="password"
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    className={`w-full px-3 py-2 border rounded-lg text-sm text-brand-ink focus:outline-none focus:ring-2 focus:ring-brand-primary focus:border-transparent ${
                      passwordMismatch
                        ? "border-red-500"
                        : "border-brand-border"
                    }`}
                  />
                </div>
                {passwordMismatch && (
                  <p className="text-sm text-red-600">Passwords do not match</p>
                )}
                {passwordError && (
                  <p className="text-sm text-red-600">{passwordError}</p>
                )}
                <div className="flex gap-2">
                  <Button
                    onClick={handleSavePassword}
                    disabled={!canSubmitPassword || isLoadingPassword}
                    className="bg-brand-gold hover:bg-brand-gold-dark text-white min-h-[44px]"
                    size="sm"
                  >
                    {isLoadingPassword ? "Updating..." : "Update password"}
                  </Button>
                  <Button
                    onClick={handleCancelPassword}
                    disabled={isLoadingPassword}
                    variant="secondary"
                    className="border border-brand-border text-brand-ink hover:bg-gray-50 min-h-[44px]"
                    size="sm"
                  >
                    Cancel
                  </Button>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Account Actions Section */}
      <div>
        <h2 className="font-sans text-xs font-bold uppercase tracking-widest text-role-teacher-muted mb-4">
          Account actions
        </h2>
        <div className="bg-white border border-red-200 rounded-2xl p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="font-semibold text-sm text-brand-ink">Sign out</p>
              <p className="text-xs text-role-teacher-body">
                You will need to sign in again on this device
              </p>
            </div>
            <button
              onClick={handleSignOut}
              className="bg-white border border-red-200 text-red-600 rounded-full px-4 py-2 text-sm font-medium hover:bg-red-50 focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2 min-h-[44px]"
            >
              Sign out
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
