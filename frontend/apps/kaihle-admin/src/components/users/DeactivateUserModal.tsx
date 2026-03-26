import { Button } from "@kaihle/ui";

interface DeactivateUserModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => void;
  userName: string;
  userEmail: string;
  isLoading?: boolean;
}

export function DeactivateUserModal({
  isOpen,
  onClose,
  onConfirm,
  userName,
  userEmail,
  isLoading = false,
}: DeactivateUserModalProps) {
  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-labelledby="deactivate-modal-title"
    >
      <div
        className="bg-white rounded-2xl shadow-xl max-w-md w-full mx-4 p-6"
        onClick={(e) => e.stopPropagation()}
      >
        <h2
          id="deactivate-modal-title"
          className="font-['Inter'] text-base font-semibold text-role-admin-ink"
        >
          Deactivate user
        </h2>
        <p className="font-['Inter'] text-sm text-gray-600 leading-relaxed mt-2">
          Are you sure you want to deactivate{" "}
          <span className="font-medium">{userName}</span> ({userEmail})? This
          action will prevent them from logging in.
        </p>
        <div className="flex gap-3 justify-end mt-6">
          <button
            onClick={onClose}
            className="border border-gray-200 text-gray-600 rounded-xl px-4 py-2 text-sm font-['Inter'] min-h-[44px] hover:bg-gray-50 transition-colors focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2"
            disabled={isLoading}
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            className="bg-red-600 text-white rounded-xl px-4 py-2 text-sm font-['Inter'] min-h-[44px] hover:bg-red-700 transition-colors focus-visible:ring-2 focus-visible:ring-red-500 focus-visible:ring-offset-2 disabled:opacity-50"
            disabled={isLoading}
            data-testid="deactivate-confirm-button"
          >
            {isLoading ? "Deactivating..." : "Deactivate"}
          </button>
        </div>
      </div>
    </div>
  );
}
