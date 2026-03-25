import { useState, useCallback } from "react";
import { toast } from "@kaihle/ui";
import { apiClient } from "@kaihle/auth";
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

interface ParentSettingsProps {
  user: ParentUser;
  children: Child[];
  onLogout: () => void;
}

export function ParentSettings({
  user,
  children,
  onLogout,
}: ParentSettingsProps) {
  const [nameEditOpen, setNameEditOpen] = useState(false);
  const [passwordEditOpen, setPasswordEditOpen] = useState(false);

  const handleNameSave = useCallback(
    async (firstName: string, lastName: string) => {
      try {
        await apiClient.patch("/api/v1/users/me", {
          first_name: firstName,
          last_name: lastName,
        });
        toast.success("Name updated");
        setNameEditOpen(false);
      } catch {
        toast.error("Something went wrong. Please try again.");
      }
    },
    [],
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
    onLogout();
  }, [onLogout]);

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

        <ChildrenSection children={children} />

        <AccountActionsSection onSignOut={handleSignOut} />
      </div>
    </div>
  );
}
