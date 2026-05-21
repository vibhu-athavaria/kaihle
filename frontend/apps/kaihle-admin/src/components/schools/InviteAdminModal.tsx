import { useState } from "react";
import { Modal } from "@kaihle/ui";
import { Button, Input } from "@kaihle/ui";
import { useInviteSchoolAdmin } from "../../hooks/useKaihleAdmin";

interface Props {
  schoolId: string;
  schoolName: string;
  open: boolean;
  onClose: () => void;
}

function validateEmail(email: string): string | null {
  if (!email.trim()) return "Email is required";
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email))
    return "Please enter a valid email address";
  return null;
}

export function InviteAdminModal({
  schoolId,
  schoolName,
  open,
  onClose,
}: Props) {
  const invite = useInviteSchoolAdmin(schoolId);
  const [form, setForm] = useState({
    email: "",
    first_name: "",
    last_name: "",
  });
  const [errors, setErrors] = useState<Record<string, string>>({});

  const validate = (): boolean => {
    const next: Record<string, string> = {};
    const emailErr = validateEmail(form.email);
    if (emailErr) next.email = emailErr;
    if (!form.first_name.trim()) next.first_name = "First name is required";
    if (!form.last_name.trim()) next.last_name = "Last name is required";
    setErrors(next);
    return Object.keys(next).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!validate()) return;
    try {
      await invite.mutateAsync(form);
      setForm({ email: "", first_name: "", last_name: "" });
      onClose();
    } catch {
      setErrors({
        submit: "Failed to send invite. The email may already be registered.",
      });
    }
  };

  const handleClose = () => {
    setForm({ email: "", first_name: "", last_name: "" });
    setErrors({});
    onClose();
  };

  return (
    <Modal
      open={open}
      onOpenChange={handleClose}
      title={`Invite admin to ${schoolName}`}
    >
      <form onSubmit={handleSubmit} className="space-y-4 mt-2">
        <Input
          label="Email"
          type="email"
          value={form.email}
          onChange={(e) => setForm({ ...form, email: e.target.value })}
          error={errors.email}
          placeholder="admin@school.com"
        />
        <div className="grid grid-cols-2 gap-3">
          <Input
            label="First name"
            value={form.first_name}
            onChange={(e) => setForm({ ...form, first_name: e.target.value })}
            error={errors.first_name}
            placeholder="Jane"
          />
          <Input
            label="Last name"
            value={form.last_name}
            onChange={(e) => setForm({ ...form, last_name: e.target.value })}
            error={errors.last_name}
            placeholder="Doe"
          />
        </div>

        <p className="text-xs text-role-admin-muted">
          A magic link will be sent to this email address to complete setup.
        </p>

        {errors.submit && (
          <p className="text-xs text-brand-red">{errors.submit}</p>
        )}

        <div className="flex justify-end gap-3 pt-2">
          <Button type="button" variant="secondary" onClick={handleClose}>
            Cancel
          </Button>
          <Button type="submit" loading={invite.isPending}>
            Send invite
          </Button>
        </div>
      </form>
    </Modal>
  );
}
