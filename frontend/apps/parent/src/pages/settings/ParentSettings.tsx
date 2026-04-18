import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth, useAuthStore, apiClient } from "@kaihle/auth";
import { toast } from "@kaihle/ui";
import { AccountSection } from "../../components/settings/AccountSection";
import { ChildrenSection } from "../../components/settings/ChildrenSection";
import { AccountActionsSection } from "../../components/settings/AccountActionsSection";

interface ParentUser {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
}

interface Child {
  id: string;
  first_name: string;
  last_name: string;
  grade: string;
  school_name: string;
}

export function ParentSettings() {
  const { logout } = useAuth();
  const navigate = useNavigate();
  const schoolId = useAuthStore((state) => state.user?.school_id);
  const [user, setUser] = useState<ParentUser | null>(null);
  const [children, setChildren] = useState<Child[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [nameEditOpen, setNameEditOpen] = useState(false);
  const [passwordEditOpen, setPasswordEditOpen] = useState(false);

  useEffect(() => {
    let cancelled = false;

    Promise.all([
      apiClient.get<ParentUser>(`/api/v1/schools/${schoolId}/users/me`),
      apiClient.get<Child[]>("/api/v1/parent/children"),
    ])
      .then(([userRes, childrenRes]) => {
        if (!cancelled) {
          setUser(userRes.data);
          setChildren(childrenRes.data);
        }
      })
      .catch((err) => {
        console.error("Failed to load parent settings data:", err);
        if (!cancelled) {
          setError("Failed to load settings. Please try again.");
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [schoolId]);

  const handleNameSave = useCallback(
    async (firstName: string, lastName: string) => {
      if (!schoolId) return;
      try {
        const res = await apiClient.patch<ParentUser>(
          `/api/v1/schools/${schoolId}/users/me`,
          {
            first_name: firstName,
            last_name: lastName,
          },
        );
        setUser(res.data);
        toast.success("Name updated");
        setNameEditOpen(false);
      } catch {
        toast.error("Something went wrong. Please try again.");
      }
    },
    [schoolId],
  );

  const handlePasswordChange = useCallback(
    async (currentPassword: string, newPassword: string) => {
      try {
        await apiClient.post("/api/v1/auth/change-password", {
          current_password: currentPassword,
          new_password: newPassword,
        });
        toast.success("Password updated");
        setPasswordEditOpen(false);
      } catch (err) {
        const error = err as {
          response?: { status?: number; data?: { detail?: string } };
        };
        if (error.response?.status === 400) {
          throw new Error("Current password is incorrect");
        }
        throw new Error("Something went wrong. Please try again.");
      }
    },
    [],
  );

  const openNameEdit = useCallback(() => {
    setNameEditOpen(true);
    setPasswordEditOpen(false);
  }, []);

  const openPasswordEdit = useCallback(() => {
    setPasswordEditOpen(true);
    setNameEditOpen(false);
  }, []);

  const handleSignOut = useCallback(async () => {
    try {
      await apiClient.post("/api/v1/auth/logout", {});
    } catch {
      // Ignore logout errors
    }
    logout();
    navigate("/login");
  }, [logout, navigate]);

  if (loading) {
    return (
      <div className="min-h-screen bg-role-parent-bg flex items-center justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-primary" />
      </div>
    );
  }

  if (error || !user) {
    return (
      <div className="px-4 py-8 max-w-lg mx-auto">
        <div className="bg-red-50 border border-red-200 rounded-2xl p-6 text-center">
          <p className="text-sm text-red-600">
            {error || "Failed to load user data."}
          </p>
          <button
            onClick={() => window.location.reload()}
            className="mt-4 bg-white border border-red-200 text-red-600 rounded-full px-4 py-2 text-sm
                       hover:bg-red-50 transition-colors
                       focus:outline-none focus:ring-2 focus:ring-red-200 focus:ring-offset-1
                       min-h-[44px]"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="px-4 py-8 max-w-lg mx-auto">
      <h1 className="font-lora text-2xl font-semibold text-gray-900 mb-6">
        Settings
      </h1>

      <div className="flex flex-col gap-4">
        <AccountSection
          user={user}
          nameEditOpen={nameEditOpen}
          passwordEditOpen={passwordEditOpen}
          onOpenNameEdit={openNameEdit}
          onOpenPasswordEdit={openPasswordEdit}
          onNameSave={handleNameSave}
          onNameCancel={() => setNameEditOpen(false)}
          onPasswordSave={handlePasswordChange}
          onPasswordCancel={() => setPasswordEditOpen(false)}
        />

        <ChildrenSection items={children} />

        <AccountActionsSection onSignOut={handleSignOut} />
      </div>
    </div>
  );
}
