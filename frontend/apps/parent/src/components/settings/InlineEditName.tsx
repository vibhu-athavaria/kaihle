import React from "react";

interface InlineEditNameProps {
  currentFirstName: string;
  currentLastName: string;
  onSave: (firstName: string, lastName: string) => Promise<void>;
  onCancel: () => void;
}

export function InlineEditName({
  currentFirstName,
  currentLastName,
  onSave,
  onCancel,
}: InlineEditNameProps) {
  const [firstName, setFirstName] = React.useState(currentFirstName);
  const [lastName, setLastName] = React.useState(currentLastName);
  const [saving, setSaving] = React.useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!firstName.trim()) return;
    setSaving(true);
    try {
      await onSave(firstName.trim(), lastName.trim());
    } finally {
      setSaving(false);
    }
  };

  const isValid = firstName.trim().length > 0;

  return (
    <form
      onSubmit={handleSubmit}
      className="px-6 py-4 bg-gray-50 border-t border-gray-100"
    >
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label
            htmlFor="firstName"
            className="block text-xs font-medium text-gray-700 mb-1"
          >
            First name
          </label>
          <input
            type="text"
            id="firstName"
            name="firstName"
            value={firstName}
            onChange={(e) => setFirstName(e.target.value)}
            className="w-full bg-white border border-gray-300 rounded-lg px-3 py-2 text-sm
                       focus:outline-none focus:ring-2 focus:ring-gray-400 focus:border-gray-400"
            autoComplete="given-name"
          />
        </div>
        <div>
          <label
            htmlFor="lastName"
            className="block text-xs font-medium text-gray-700 mb-1"
          >
            Last name
          </label>
          <input
            type="text"
            id="lastName"
            name="lastName"
            value={lastName}
            onChange={(e) => setLastName(e.target.value)}
            className="w-full bg-white border border-gray-300 rounded-lg px-3 py-2 text-sm
                       focus:outline-none focus:ring-2 focus:ring-gray-400 focus:border-gray-400"
            autoComplete="family-name"
          />
        </div>
      </div>
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
