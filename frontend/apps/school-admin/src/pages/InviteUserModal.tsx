import { useState } from "react";
import { Button, Input, Modal } from "@kaihle/ui";
import { UserRole } from "@kaihle/types";
import { useSchoolStudents } from "../hooks/useSchoolAdmin";

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
    student_ids?: string[];
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
  const [selectedStudentIds, setSelectedStudentIds] = useState<string[]>([]);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [isSubmitting, setIsSubmitting] = useState(false);

  const { data: students = [], isLoading: studentsLoading } =
    useSchoolStudents();

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
        ...(role === UserRole.PARENT && selectedStudentIds.length > 0
          ? { student_ids: selectedStudentIds }
          : {}),
      });
      setFirstName("");
      setLastName("");
      setEmail("");
      setRole(defaultRole);
      setSelectedStudentIds([]);
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
    <Modal
      open={isOpen}
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
      title={getTitle()}
    >
      <form onSubmit={handleSubmit} className="space-y-4 mt-4">
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
            onChange={(e) => {
              const newRole = e.target.value as typeof role;
              setRole(newRole);
              if (newRole !== UserRole.PARENT) {
                setSelectedStudentIds([]);
              }
            }}
            className="w-full px-4 py-2.5 rounded-xl border border-brand-border bg-white text-brand-ink font-sans text-sm focus:outline-none focus:ring-2 focus:ring-brand-primary/30 focus:border-brand-primary"
          >
            {roleOptions.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>

        {role === UserRole.PARENT && (
          <div>
            <label className="block text-sm font-semibold text-brand-ink mb-1.5">
              Link to students{" "}
              <span className="text-brand-muted font-normal">(optional)</span>
            </label>
            {studentsLoading ? (
              <div className="animate-pulse h-8 bg-brand-border rounded-lg" />
            ) : students.length === 0 ? (
              <p className="text-xs text-brand-muted">
                No students in this school yet.
              </p>
            ) : (
              <div className="max-h-40 overflow-y-auto border border-brand-border rounded-xl divide-y divide-brand-border">
                {students.map((s) => (
                  <label
                    key={s.id}
                    className="flex items-center gap-2.5 px-3 py-2 hover:bg-gray-50 cursor-pointer"
                  >
                    <input
                      type="checkbox"
                      checked={selectedStudentIds.includes(String(s.id))}
                      onChange={(e) => {
                        const id = String(s.id);
                        setSelectedStudentIds((prev) =>
                          e.target.checked
                            ? [...prev, id]
                            : prev.filter((x) => x !== id),
                        );
                      }}
                      className="w-4 h-4 rounded accent-brand-primary"
                    />
                    <span className="text-sm text-brand-ink">
                      {s.first_name} {s.last_name}
                    </span>
                  </label>
                ))}
              </div>
            )}
          </div>
        )}

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
    </Modal>
  );
}
