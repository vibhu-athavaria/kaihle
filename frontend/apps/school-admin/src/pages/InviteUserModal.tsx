import { useState } from "react";
import { Button } from "@kaihle/ui";
import { Input } from "@kaihle/ui";
import { UserRole } from "@kaihle/types";
import { X } from "lucide-react";

type SchoolRole =
  | typeof UserRole.TEACHER
  | typeof UserRole.STUDENT
  | typeof UserRole.PARENT;

interface InviteUserModalProps {
  isOpen: boolean;
  onClose: () => void;
  onInvite: (data: {
    first_name: string;
    last_name: string;
    email: string;
    role: SchoolRole;
  }) => void;
  defaultRole?: SchoolRole;
}

const roleOptions: { value: SchoolRole; label: string }[] = [
  { value: UserRole.TEACHER, label: "Teacher" },
  { value: UserRole.STUDENT, label: "Student" },
  { value: UserRole.PARENT, label: "Parent" },
];

export function InviteUserModal({
  isOpen,
  onClose,
  onInvite,
  defaultRole = UserRole.TEACHER,
}: InviteUserModalProps) {
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [email, setEmail] = useState("");
  const [role, setRole] = useState(defaultRole);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [isSubmitting, setIsSubmitting] = useState(false);

  if (!isOpen) return null;

  const validate = () => {
    const newErrors: Record<string, string> = {};
    if (!firstName.trim()) {
      newErrors.firstName = "First name is required";
    }
    if (!lastName.trim()) {
      newErrors.lastName = "Last name is required";
    }
    if (!email.trim()) {
      newErrors.email = "Email is required";
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      newErrors.email = "Enter a valid email address";
    }
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!validate()) return;

    setIsSubmitting(true);
    try {
      await onInvite({
        first_name: firstName.trim(),
        last_name: lastName.trim(),
        email: email.trim().toLowerCase(),
        role,
      });
      setFirstName("");
      setLastName("");
      setEmail("");
      setRole(defaultRole);
      setErrors({});
      onClose();
    } catch {
      // Error handling done by caller
    } finally {
      setIsSubmitting(false);
    }
  };

  const getTitle = () => {
    switch (role) {
      case UserRole.TEACHER:
        return "Invite a teacher";
      case UserRole.STUDENT:
        return "Invite a student";
      case UserRole.PARENT:
        return "Invite a parent";
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div
        className="absolute inset-0 bg-black/40"
        onClick={onClose}
        aria-hidden="true"
      />
      <div
        className="relative bg-white rounded-2xl border border-brand-border shadow-xl p-6 w-full max-w-md mx-4 animate-in fade-in zoom-in-95 duration-200"
        role="dialog"
        aria-modal="true"
        aria-labelledby="modal-title"
      >
        <button
          onClick={onClose}
          className="absolute top-4 right-4 p-1 text-brand-muted hover:text-brand-ink rounded-full hover:bg-gray-100"
          aria-label="Close"
        >
          <X className="w-5 h-5" />
        </button>

        <h2
          id="modal-title"
          className="text-xl font-display font-bold text-brand-ink mb-6"
        >
          {getTitle()}
        </h2>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <Input
              id="firstName"
              label="First name"
              type="text"
              value={firstName}
              onChange={(e) => setFirstName(e.target.value)}
              placeholder="Enter first name"
              error={errors.firstName}
            />
          </div>

          <div>
            <Input
              id="lastName"
              label="Last name"
              type="text"
              value={lastName}
              onChange={(e) => setLastName(e.target.value)}
              placeholder="Enter last name"
              error={errors.lastName}
            />
          </div>

          <div>
            <Input
              id="email"
              label="Email address"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="Enter email address"
              error={errors.email}
            />
          </div>

          <div>
            <label
              htmlFor="role"
              className="block text-sm font-semibold text-brand-ink mb-1.5"
            >
              Role
            </label>
            <select
              id="role"
              value={role}
              onChange={(e) => setRole(e.target.value as typeof role)}
              className="w-full px-4 py-2.5 rounded-xl border border-brand-border bg-white text-brand-ink font-sans text-sm focus:outline-none focus:ring-2 focus:ring-brand-primary/30 focus:border-brand-primary"
            >
              {roleOptions.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>

          <div className="flex gap-3 pt-4">
            <Button
              type="button"
              variant="secondary"
              onClick={onClose}
              className="flex-1"
            >
              Cancel
            </Button>
            <Button
              type="submit"
              variant="primary"
              loading={isSubmitting}
              className="flex-1"
            >
              Send invite →
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
