import { useMutation } from "@tanstack/react-query";
import { apiClient } from "@kaihle/auth";
import { useAuth } from "@kaihle/auth";

export function AccountActionsSection() {
  const { logout } = useAuth();

  const logoutMutation = useMutation({
    mutationFn: async () => {
      await apiClient.post("/api/v1/auth/logout");
    },
    onSuccess: () => {
      logout();
    },
    onError: () => {
      // Even if the API call fails, log out locally
      logout();
    },
  });

  const handleSignOut = () => {
    logoutMutation.mutate();
  };

  return (
    <div className="bg-white rounded-2xl border border-brand-border-soft shadow-sm">
      <h2 className="font-display text-base text-brand-ink px-6 pt-5 pb-3 border-b border-brand-border-soft">
        Account actions
      </h2>

      <div className="px-6 py-5">
        <button
          type="button"
          onClick={handleSignOut}
          disabled={logoutMutation.isPending}
          className="border border-red-200 text-red-600 rounded-xl px-4 py-2 text-sm font-medium w-full hover:bg-red-50 transition-colors min-h-[44px] disabled:opacity-60 disabled:cursor-not-allowed focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2"
        >
          {logoutMutation.isPending ? (
            <span className="flex items-center justify-center gap-2">
              <span className="animate-spin rounded-full h-4 w-4 border-b-2 border-red-600" />
              Signing out...
            </span>
          ) : (
            "Sign out"
          )}
        </button>
        <p className="text-xs text-brand-muted mt-2 text-center">
          You'll need to sign in again on this device
        </p>
      </div>
    </div>
  );
}
