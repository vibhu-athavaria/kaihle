/**
 * EditUserDrawer component for Kaihle Admin.
 *
 * Provides inline user editing in a right-side drawer using Radix Dialog.
 * Implements focus trap, escape to close, and focus return per Rule 21.
 */

import { useEffect, useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { X, Loader2 } from "lucide-react";
import { PlatformUser, UserRole } from "./PlatformUserTable";

export interface EditUserDrawerProps {
  user: PlatformUser | null;
  isOpen: boolean;
  onClose: () => void;
  onSave: (data: {
    userId: string;
    schoolId: string;
    firstName: string;
    lastName: string;
    role: UserRole;
    password?: string;
  }) => Promise<void>;
  onDeactivate: (userId: string, schoolId: string) => Promise<void>;
  isSaving?: boolean;
  isDeactivating?: boolean;
}

const roleOptions: { value: UserRole; label: string }[] = [
  { value: "TEACHER", label: "Teacher" },
  { value: "SCHOOL_ADMIN", label: "School Admin" },
  { value: "PARENT", label: "Parent" },
  { value: "STUDENT", label: "Student" },
];

function formatDate(dateString: string | null): string {
  if (!dateString) return "Never";
  const date = new Date(dateString);
  return date.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function getRoleBadgeClass(role: UserRole): string {
  const styles: Record<UserRole, string> = {
    KAIHLE_ADMIN: "bg-purple-50 text-purple-700",
    SCHOOL_ADMIN: "bg-blue-50 text-blue-700",
    TEACHER: "bg-amber-50 text-amber-700",
    STUDENT: "bg-green-50 text-green-700",
    PARENT: "bg-pink-50 text-pink-600",
  };
  return styles[role] || "bg-gray-50 text-gray-700";
}

export function EditUserDrawer({
  user,
  isOpen,
  onClose,
  onSave,
  onDeactivate,
  isSaving = false,
  isDeactivating = false,
}: EditUserDrawerProps) {
  const [firstName, setFirstName] = useState(user?.first_name ?? "");
  const [lastName, setLastName] = useState(user?.last_name ?? "");
  const [role, setRole] = useState<UserRole>(user?.role ?? "TEACHER");
  const [password, setPassword] = useState("");
  const [showDeactivateConfirm, setShowDeactivateConfirm] = useState(false);

  // Reset form when user changes
  useEffect(() => {
    if (user) {
      setFirstName(user.first_name);
      setLastName(user.last_name);
      setRole(user.role);
      setPassword("");
      setShowDeactivateConfirm(false);
    }
  }, [user]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!user) return;

    await onSave({
      userId: user.id,
      schoolId: user.school_id || "platform",
      firstName,
      lastName,
      role,
      password: password || undefined,
    });
  };

  const handleDeactivate = async () => {
    if (!user) return;
    await onDeactivate(user.id, user.school_id || "platform");
    setShowDeactivateConfirm(false);
  };

  const fullName = user ? `${user.first_name} ${user.last_name}` : "";

  return (
    <Dialog.Root open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-black/20 z-50" />
        <Dialog.Content
          className="fixed right-0 top-0 bottom-0 w-[360px] bg-white shadow-xl z-50 flex flex-col outline-none"
          aria-describedby="edit-user-description"
        >
          {/* Header */}
          <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
            <Dialog.Title className="font-['Inter'] text-base font-semibold text-gray-900">
              Edit user
            </Dialog.Title>
            <Dialog.Close asChild>
              <button
                className="p-2 hover:bg-gray-100 rounded-lg transition-colors focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2"
                aria-label="Close"
              >
                <X className="w-5 h-5 text-gray-500" />
              </button>
            </Dialog.Close>
          </div>

          {!user ? (
            <div className="flex-1 flex items-center justify-center p-6">
              <p className="text-gray-500 font-['Inter'] text-sm">
                No user selected
              </p>
            </div>
          ) : (
            <>
              {/* User Identity (Read-only) */}
              <div className="px-5 py-4 border-b border-gray-100 bg-gray-50/50">
                <div className="space-y-2">
                  <div>
                    <span className="text-xs font-medium text-gray-500 uppercase tracking-wide">
                      Name
                    </span>
                    <p className="font-['Inter'] text-sm font-medium text-gray-900">
                      {fullName}
                    </p>
                  </div>
                  <div>
                    <span className="text-xs font-medium text-gray-500 uppercase tracking-wide">
                      Email
                    </span>
                    <p className="font-['Inter'] text-sm text-gray-700">
                      {user.email}
                    </p>
                  </div>
                  <div className="flex gap-4">
                    <div>
                      <span className="text-xs font-medium text-gray-500 uppercase tracking-wide">
                        School
                      </span>
                      <p className="font-['Inter'] text-sm text-gray-700">
                        {user.school_name || "—"}
                      </p>
                    </div>
                    <div>
                      <span className="text-xs font-medium text-gray-500 uppercase tracking-wide">
                        Role
                      </span>
                      <span
                        className={`ml-2 inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${getRoleBadgeClass(user.role)}`}
                      >
                        {user.role.replace("_", " ")}
                      </span>
                    </div>
                  </div>
                  <div>
                    <span className="text-xs font-medium text-gray-500 uppercase tracking-wide">
                      Last active
                    </span>
                    <p className="font-['Inter'] text-sm text-gray-700">
                      {formatDate(user.last_active)}
                    </p>
                  </div>
                </div>
              </div>

              {/* Editable Form */}
              <form onSubmit={handleSubmit} className="flex-1 overflow-y-auto">
                <div className="p-5 space-y-4">
                  <div>
                    <label
                      htmlFor="firstName"
                      className="block text-sm font-medium text-gray-700 mb-1.5"
                    >
                      First name <span className="text-red-500">*</span>
                    </label>
                    <input
                      id="firstName"
                      type="text"
                      value={firstName}
                      onChange={(e) => setFirstName(e.target.value)}
                      required
                      className="w-full bg-white border border-gray-200 rounded-lg px-3 py-2 text-sm font-['Inter'] text-gray-900 placeholder-gray-400 focus:border-brand-primary focus:ring-1 focus:ring-brand-primary/20 outline-none"
                    />
                  </div>

                  <div>
                    <label
                      htmlFor="lastName"
                      className="block text-sm font-medium text-gray-700 mb-1.5"
                    >
                      Last name <span className="text-red-500">*</span>
                    </label>
                    <input
                      id="lastName"
                      type="text"
                      value={lastName}
                      onChange={(e) => setLastName(e.target.value)}
                      required
                      className="w-full bg-white border border-gray-200 rounded-lg px-3 py-2 text-sm font-['Inter'] text-gray-900 placeholder-gray-400 focus:border-brand-primary focus:ring-1 focus:ring-brand-primary/20 outline-none"
                    />
                  </div>

                  <div>
                    <label
                      htmlFor="role"
                      className="block text-sm font-medium text-gray-700 mb-1.5"
                    >
                      Role <span className="text-red-500">*</span>
                    </label>
                    <select
                      id="role"
                      value={role}
                      onChange={(e) => setRole(e.target.value as UserRole)}
                      required
                      disabled={user.role === "KAIHLE_ADMIN"}
                      className="w-full bg-white border border-gray-200 rounded-lg px-3 py-2 text-sm font-['Inter'] text-gray-900 focus:border-brand-primary focus:ring-1 focus:ring-brand-primary/20 outline-none disabled:bg-gray-50 disabled:text-gray-500"
                    >
                      {roleOptions.map((option) => (
                        <option key={option.value} value={option.value}>
                          {option.label}
                        </option>
                      ))}
                    </select>
                    {user.role === "KAIHLE_ADMIN" && (
                      <p className="mt-1 text-xs text-gray-500">
                        KAIHLE_ADMIN role cannot be changed
                      </p>
                    )}
                  </div>

                  <div>
                    <label
                      htmlFor="password"
                      className="block text-sm font-medium text-gray-700 mb-1.5"
                    >
                      New password
                    </label>
                    <input
                      id="password"
                      type="password"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      minLength={8}
                      placeholder="Leave blank to keep current"
                      className="w-full bg-white border border-gray-200 rounded-lg px-3 py-2 text-sm font-['Inter'] text-gray-900 placeholder-gray-400 focus:border-brand-primary focus:ring-1 focus:ring-brand-primary/20 outline-none"
                    />
                    <p className="mt-1 text-xs text-gray-500">
                      Minimum 8 characters. Leave blank to keep current
                      password.
                    </p>
                  </div>
                </div>

                {/* Save Button */}
                <div className="px-5 py-4 border-t border-gray-100">
                  <button
                    type="submit"
                    disabled={isSaving}
                    className="w-full bg-brand-primary text-white rounded-full px-4 py-2.5 text-sm font-medium font-['Inter'] hover:bg-brand-primary/90 transition-colors focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                  >
                    {isSaving ? (
                      <>
                        <Loader2 className="w-4 h-4 animate-spin" />
                        Saving...
                      </>
                    ) : (
                      "Save changes"
                    )}
                  </button>
                </div>
              </form>

              {/* Danger Zone */}
              <div className="px-5 py-4 border-t border-gray-200 mt-auto">
                {!showDeactivateConfirm ? (
                  <button
                    type="button"
                    onClick={() => setShowDeactivateConfirm(true)}
                    disabled={isDeactivating || !user.is_active}
                    className="w-full border border-red-300 text-red-600 rounded-full px-4 py-2.5 text-sm font-medium font-['Inter'] hover:bg-red-50 transition-colors focus-visible:ring-2 focus-visible:ring-red-500 focus-visible:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {user.is_active ? "Deactivate user" : "User deactivated"}
                  </button>
                ) : (
                  <div className="space-y-3">
                    <p className="text-sm text-gray-700 font-['Inter']">
                      This will prevent{" "}
                      <span className="font-medium">{fullName}</span> from
                      logging in. Confirm?
                    </p>
                    <div className="flex gap-2">
                      <button
                        type="button"
                        onClick={() => setShowDeactivateConfirm(false)}
                        className="flex-1 border border-gray-200 text-gray-700 rounded-full px-4 py-2 text-sm font-medium font-['Inter'] hover:bg-gray-50 transition-colors"
                      >
                        Cancel
                      </button>
                      <button
                        type="button"
                        onClick={handleDeactivate}
                        disabled={isDeactivating}
                        className="flex-1 bg-red-600 text-white rounded-full px-4 py-2 text-sm font-medium font-['Inter'] hover:bg-red-700 transition-colors focus-visible:ring-2 focus-visible:ring-red-500 focus-visible:ring-offset-2 disabled:opacity-50 flex items-center justify-center gap-2"
                      >
                        {isDeactivating ? (
                          <>
                            <Loader2 className="w-4 h-4 animate-spin" />
                            ...
                          </>
                        ) : (
                          "Deactivate"
                        )}
                      </button>
                    </div>
                  </div>
                )}
              </div>
            </>
          )}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
