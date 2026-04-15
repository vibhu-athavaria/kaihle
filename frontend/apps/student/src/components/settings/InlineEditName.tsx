import { useState } from "react";

interface InlineEditNameProps {
  initialFirstName: string;
  initialLastName: string;
  onSave: (firstName: string, lastName: string) => void;
  onCancel: () => void;
  isLoading: boolean;
  error: string | null;
}

export function InlineEditName({
  initialFirstName,
  initialLastName,
  onSave,
  onCancel,
  isLoading,
  error,
}: InlineEditNameProps) {
  const [firstName, setFirstName] = useState(initialFirstName);
  const [lastName, setLastName] = useState(initialLastName);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!isLoading) {
      onSave(firstName, lastName);
    }
  };

  return (
    <form
      onSubmit={handleSubmit}
      className="px-6 pb-4 pt-1 bg-brand-border-soft/50 border-b border-brand-border-soft"
    >
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div>
          <input
            type="text"
            value={firstName}
            onChange={(e) => setFirstName(e.target.value)}
            placeholder="First name"
            className="w-full rounded-lg border border-brand-border px-3 py-2 text-sm transition-colors focus:border-brand-primary focus:ring-1 focus:ring-brand-primary/20 outline-none"
            disabled={isLoading}
            aria-label="First name"
          />
        </div>
        <div>
          <input
            type="text"
            value={lastName}
            onChange={(e) => setLastName(e.target.value)}
            placeholder="Last name"
            className="w-full rounded-lg border border-brand-border px-3 py-2 text-sm transition-colors focus:border-brand-primary focus:ring-1 focus:ring-brand-primary/20 outline-none"
            disabled={isLoading}
            aria-label="Last name"
          />
        </div>
      </div>
      {error && <div className="text-red-500 text-xs mt-1">{error}</div>}
      <div className="flex gap-2 mt-3">
        <button
          type="submit"
          disabled={isLoading}
          className="bg-brand-primary text-white rounded-lg px-4 py-2 text-sm disabled:opacity-60 disabled:cursor-not-allowed min-h-[44px] focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2"
        >
          {isLoading ? (
            <span className="flex items-center gap-2">
              <span className="animate-spin rounded-full h-4 w-4 border-b-2 border-white" />
              Saving...
            </span>
          ) : (
            "Save"
          )}
        </button>
        <button
          type="button"
          onClick={onCancel}
          disabled={isLoading}
          className="border border-brand-border text-brand-body rounded-lg px-4 py-2 text-sm disabled:opacity-60 min-h-[44px] focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2"
        >
          Cancel
        </button>
      </div>
    </form>
  );
}
