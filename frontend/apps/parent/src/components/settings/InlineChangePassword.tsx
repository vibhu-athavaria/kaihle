import React from "react";

interface InlineChangePasswordProps {
  onSave: (currentPassword: string, newPassword: string) => Promise<void>;
  onCancel: () => void;
}

export function InlineChangePassword({
  onSave,
  onCancel,
}: InlineChangePasswordProps) {
  const [currentPassword, setCurrentPassword] = React.useState("");
  const [newPassword, setNewPassword] = React.useState("");
  const [confirmPassword, setConfirmPassword] = React.useState("");
  const [saving, setSaving] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  const passwordsMatch = newPassword === confirmPassword;
  const isValid =
    currentPassword.length > 0 && newPassword.length >= 8 && passwordsMatch;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!isValid) return;
    setSaving(true);
    setError(null);
    try {
      await onSave(currentPassword, newPassword);
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
    } catch (err) {
      const message =
        err instanceof Error
          ? err.message
          : "Something went wrong. Please try again.";
      setError(message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <form
      onSubmit={handleSubmit}
      className="px-6 py-4 bg-gray-50 border-t border-gray-100"
    >
      <div className="flex flex-col gap-3">
        <div>
          <label
            htmlFor="currentPassword"
            className="block text-xs font-medium text-gray-700 mb-1"
          >
            Current password
          </label>
          <input
            type="password"
            id="currentPassword"
            name="currentPassword"
            value={currentPassword}
            onChange={(e) => setCurrentPassword(e.target.value)}
            className="w-full bg-white border border-gray-300 rounded-lg px-3 py-2 text-sm
                       focus:outline-none focus:ring-2 focus:ring-gray-400 focus:border-gray-400"
            autoComplete="current-password"
          />
        </div>
        <div>
          <label
            htmlFor="newPassword"
            className="block text-xs font-medium text-gray-700 mb-1"
          >
            New password
          </label>
          <input
            type="password"
            id="newPassword"
            name="newPassword"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            className="w-full bg-white border border-gray-300 rounded-lg px-3 py-2 text-sm
                       focus:outline-none focus:ring-2 focus:ring-gray-400 focus:border-gray-400"
            autoComplete="new-password"
          />
          <p className="text-xs text-gray-400 mt-1">Minimum 8 characters</p>
        </div>
        <div>
          <label
            htmlFor="confirmPassword"
            className="block text-xs font-medium text-gray-700 mb-1"
          >
            Confirm new password
          </label>
          <input
            type="password"
            id="confirmPassword"
            name="confirmPassword"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            className="w-full bg-white border border-gray-300 rounded-lg px-3 py-2 text-sm
                       focus:outline-none focus:ring-2 focus:ring-gray-400 focus:border-gray-400"
            autoComplete="new-password"
          />
          {confirmPassword.length > 0 && !passwordsMatch && (
            <p className="text-xs text-red-500 mt-1">Passwords do not match</p>
          )}
        </div>
      </div>

      {error && (
        <p className="text-sm text-red-500 mt-3" role="alert">
          {error}
        </p>
      )}

      <div className="mt-3 flex gap-2">
        <button
          type="submit"
          disabled={!isValid || saving}
          className="bg-gray-900 text-white rounded-full px-4 py-2 text-sm
                     hover:bg-gray-800 disabled:opacity-50 disabled:cursor-not-allowed
                     focus:outline-none focus:ring-2 focus:ring-gray-400 focus:ring-offset-1
                     min-h-[44px]"
        >
          {saving ? "Saving..." : "Save"}
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="bg-white border border-gray-200 text-gray-600 rounded-full px-4 py-2 text-sm
                     hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-gray-400 focus:ring-offset-1
                     min-h-[44px]"
        >
          Cancel
        </button>
      </div>
    </form>
  );
}
