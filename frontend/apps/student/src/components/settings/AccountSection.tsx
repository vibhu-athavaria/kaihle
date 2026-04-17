import { useState } from "react";
import { apiClient } from "@kaihle/auth";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { InlineEditName } from "./InlineEditName";
import { InlineChangePassword } from "./InlineChangePassword";
import { useStudentInfo } from "../../hooks/useStudentInfo";

export function AccountSection() {
  const queryClient = useQueryClient();
  const { data: studentInfo } = useStudentInfo();
  const schoolId = studentInfo?.schoolId;

  const [editingName, setEditingName] = useState(false);
  const [editingPassword, setEditingPassword] = useState(false);

  const updateNameMutation = useMutation({
    mutationFn: async (data: { first_name: string; last_name: string }) => {
      if (!schoolId) throw new Error("School ID not available");
      await apiClient.patch(`/api/v1/schools/${schoolId}/users/me`, data);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["student", "info"],
      });
      queryClient.invalidateQueries({
        queryKey: ["student", "settings", "user"],
      });
      setEditingName(false);
    },
  });

  const handleNameSave = (firstName: string, lastName: string) => {
    updateNameMutation.mutate({ first_name: firstName, last_name: lastName });
  };

  const handleNameCancel = () => {
    setEditingName(false);
  };

  const handlePasswordCancel = () => {
    setEditingPassword(false);
  };

  const handlePasswordSuccess = () => {
    setEditingPassword(false);
  };

  // Close password when name opens and vice versa
  const handleStartNameEdit = () => {
    setEditingPassword(false);
    setEditingName(true);
  };

  const handleStartPasswordEdit = () => {
    setEditingName(false);
    setEditingPassword(true);
  };

  const displayName = studentInfo
    ? `${studentInfo.firstName}${
        studentInfo.lastName ? ` ${studentInfo.lastName}` : ""
      }`
    : "—";

  return (
    <div className="bg-white rounded-2xl border border-brand-border shadow-sm">
      <h2 className="font-display text-base text-brand-ink px-6 pt-5 pb-3 border-b border-brand-border-soft">
        Account
      </h2>

      {/* Name row */}
      <div className="px-6 py-4 flex items-center justify-between">
        <div>
          <div className="font-sans text-sm font-medium text-brand-ink">
            Name
          </div>
          <div className="font-sans text-sm text-brand-muted">
            {displayName}
          </div>
        </div>
        {!editingName && (
          <button
            type="button"
            onClick={handleStartNameEdit}
            className="text-brand-primary text-sm font-medium cursor-pointer focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2 rounded min-h-[44px] px-2"
          >
            Edit
          </button>
        )}
      </div>

      {editingName && (
        <InlineEditName
          initialFirstName={studentInfo?.firstName || ""}
          initialLastName={studentInfo?.lastName || ""}
          onSave={handleNameSave}
          onCancel={handleNameCancel}
          isLoading={updateNameMutation.isPending}
          error={updateNameMutation.isError ? "Failed to update name" : null}
        />
      )}

      <div className="h-px bg-brand-border-soft mx-6" />

      {/* Email row */}
      <div className="px-6 py-4 flex items-center justify-between">
        <div>
          <div className="font-sans text-sm font-medium text-brand-ink">
            Email
          </div>
          <div className="font-sans text-sm text-brand-muted">
            {studentInfo?.email || "—"}
          </div>
        </div>
        <span className="bg-brand-border-soft text-brand-muted text-xs rounded-full px-2 py-0.5">
          Managed by school
        </span>
      </div>

      <div className="h-px bg-brand-border-soft mx-6" />

      {/* Password row */}
      <div className="px-6 py-4 flex items-center justify-between">
        <div>
          <div className="font-sans text-sm font-medium text-brand-ink">
            Password
          </div>
          <div className="font-sans text-sm text-brand-muted">
            Last changed —
          </div>
        </div>
        {!editingPassword && (
          <button
            type="button"
            onClick={handleStartPasswordEdit}
            className="text-brand-primary text-sm font-medium cursor-pointer focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2 rounded min-h-[44px] px-2"
          >
            Change
          </button>
        )}
      </div>

      {editingPassword && (
        <InlineChangePassword
          onCancel={handlePasswordCancel}
          onSuccess={handlePasswordSuccess}
        />
      )}
    </div>
  );
}
