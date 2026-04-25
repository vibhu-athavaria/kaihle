import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { apiClient, useAuthStore } from "@kaihle/auth";

export function ChangePasswordPage() {
  const navigate = useNavigate();
  const clearMustChangePassword = useAuthStore(
    (state) => state.clearMustChangePassword,
  );
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    if (newPassword !== confirmPassword) {
      setError("Passwords do not match");
      return;
    }
    if (newPassword.length < 8) {
      setError("Password must be at least 8 characters");
      return;
    }
    setLoading(true);
    try {
      await apiClient.post("/api/v1/auth/change-password", {
        current_password: currentPassword,
        new_password: newPassword,
        confirm_password: confirmPassword,
      });
      clearMustChangePassword();
      navigate("/parent");
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Failed to change password");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="bg-white p-8 rounded-xl shadow-sm w-full max-w-md">
        <h1 className="text-xl font-bold text-brand-ink mb-2">
          Change your password
        </h1>
        <p className="text-sm text-brand-muted mb-6">
          Your account requires a password change before you can continue.
        </p>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-bold uppercase tracking-wide text-brand-ink mb-1">
              Current password
            </label>
            <input
              type="password"
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
              className="w-full px-3 py-2 border border-brand-border rounded-lg text-sm outline-none focus-visible:ring-2 focus-visible:ring-brand-primary"
              required
            />
          </div>
          <div>
            <label className="block text-xs font-bold uppercase tracking-wide text-brand-ink mb-1">
              New password
            </label>
            <input
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              className="w-full px-3 py-2 border border-brand-border rounded-lg text-sm outline-none focus-visible:ring-2 focus-visible:ring-brand-primary"
              required
            />
          </div>
          <div>
            <label className="block text-xs font-bold uppercase tracking-wide text-brand-ink mb-1">
              Confirm new password
            </label>
            <input
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              className="w-full px-3 py-2 border border-brand-border rounded-lg text-sm outline-none focus-visible:ring-2 focus-visible:ring-brand-primary"
              required
            />
          </div>
          {error && <p className="text-red-500 text-xs">{error}</p>}
          <button
            type="submit"
            disabled={loading}
            className="w-full py-2.5 rounded-full text-sm font-bold bg-brand-primary text-white hover:bg-brand-dark disabled:opacity-60"
          >
            {loading ? "Updating…" : "Update password"}
          </button>
        </form>
      </div>
    </div>
  );
}
