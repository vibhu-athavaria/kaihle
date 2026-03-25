interface AccountActionsSectionProps {
  onSignOut: () => void;
}

export function AccountActionsSection({
  onSignOut,
}: AccountActionsSectionProps) {
  return (
    <div className="bg-white border border-red-100 rounded-2xl overflow-hidden">
      <div className="px-6 py-4 flex items-center justify-between">
        <div>
          <p className="text-sm font-medium text-gray-700">Sign out</p>
          <p className="text-xs text-gray-400 mt-0.5">
            You'll need to sign in again to access Kaihle.
          </p>
        </div>
        <button
          onClick={onSignOut}
          className="bg-white border border-red-200 text-red-600 rounded-full px-4 py-2 text-sm
                     hover:bg-red-50 transition-colors
                     focus:outline-none focus:ring-2 focus:ring-red-200 focus:ring-offset-1
                     min-h-[44px]"
        >
          Sign out
        </button>
      </div>
    </div>
  );
}
