import { InlineEditName } from "./InlineEditName";
import { InlineChangePassword } from "./InlineChangePassword";

interface ParentUser {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
}

interface AccountSectionProps {
  user: ParentUser;
  nameEditOpen: boolean;
  passwordEditOpen: boolean;
  onOpenNameEdit: () => void;
  onOpenPasswordEdit: () => void;
  onNameSave: (firstName: string, lastName: string) => Promise<void>;
  onNameCancel: () => void;
  onPasswordSave: (
    currentPassword: string,
    newPassword: string,
  ) => Promise<void>;
  onPasswordCancel: () => void;
}

export function AccountSection({
  user,
  nameEditOpen,
  passwordEditOpen,
  onOpenNameEdit,
  onOpenPasswordEdit,
  onNameSave,
  onNameCancel,
  onPasswordSave,
  onPasswordCancel,
}: AccountSectionProps) {
  return (
    <div className="bg-white border border-gray-200 rounded-2xl overflow-hidden">
      <div className="px-6 py-4 border-b border-gray-100">
        <h2 className="font-lora text-base font-semibold text-gray-900">
          My account
        </h2>
      </div>

      {/* Name row */}
      <div className="flex items-start justify-between px-6 py-4 border-b border-gray-100">
        <div>
          <p className="text-sm font-medium text-gray-700">Name</p>
          <p className="text-sm text-gray-500 mt-0.5">
            {user.first_name} {user.last_name}
          </p>
        </div>
        {!nameEditOpen && (
          <button
            onClick={onOpenNameEdit}
            className="text-sm text-gray-700 font-medium hover:text-gray-900 underline cursor-pointer
                       focus:outline-none focus:ring-2 focus:ring-gray-400 focus:ring-offset-1
                       min-h-[44px]"
          >
            Edit
          </button>
        )}
      </div>
      {nameEditOpen && (
        <InlineEditName
          currentFirstName={user.first_name}
          currentLastName={user.last_name}
          onSave={onNameSave}
          onCancel={onNameCancel}
        />
      )}

      {/* Email row */}
      <div
        className="flex items-start justify-between px-6 py-4 border-b border-gray-100"
        data-testid="email-row"
      >
        <div>
          <p className="text-sm font-medium text-gray-700">Email</p>
          <p className="text-sm text-gray-500 mt-0.5">{user.email}</p>
        </div>
        <span className="bg-gray-100 text-gray-500 text-xs rounded-full px-2.5 py-1">
          Managed by school
        </span>
      </div>

      {/* Password row */}
      <div className="flex items-start justify-between px-6 py-4 border-b border-gray-100 last:border-0">
        <div>
          <p className="text-sm font-medium text-gray-700">Password</p>
          <p className="text-sm text-gray-500 mt-0.5">—</p>
        </div>
        {!passwordEditOpen && (
          <button
            onClick={onOpenPasswordEdit}
            className="text-sm text-gray-700 font-medium hover:text-gray-900 underline cursor-pointer
                       focus:outline-none focus:ring-2 focus:ring-gray-400 focus:ring-offset-1
                       min-h-[44px]"
          >
            Change
          </button>
        )}
      </div>
      {passwordEditOpen && (
        <InlineChangePassword
          onSave={onPasswordSave}
          onCancel={onPasswordCancel}
        />
      )}
    </div>
  );
}
