import { useState } from "react";
import { Modal } from "@kaihle/ui";
import { Button, Input } from "@kaihle/ui";
import { useCreateSchoolAdmin } from "../../hooks/useKaihleAdmin";

interface Props {
  schoolId: string;
  schoolName: string;
  open: boolean;
  onClose: () => void;
}

const EMPTY_FORM = {
  email: "",
  first_name: "",
  last_name: "",
  password: "",
};

export function InviteAdminModal({
  schoolId,
  schoolName,
  open,
  onClose,
}: Props) {
  const create = useCreateSchoolAdmin(schoolId);
  const [form, setForm] = useState(EMPTY_FORM);
  const [errors, setErrors] = useState<Record<string, string>>({});

  const validate = (): boolean => {
    const next: Record<string, string> = {};
    if (!form.email.trim()) next.email = "Email is required";
    else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email))
      next.email = "Please enter a valid email address";
    if (!form.first_name.trim()) next.first_name = "First name is required";
    if (!form.last_name.trim()) next.last_name = "Last name is required";
    if (!form.password.trim()) next.password = "Password is required";
    else if (form.password.length < 8)
      next.password = "Password must be at least 8 characters";
    setErrors(next);
    return Object.keys(next).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!validate()) return;
    try {
      await create.mutateAsync(form);
      setForm(EMPTY_FORM);
      onClose();
    } catch (err: unknown) {
      const axiosErr = err as {
        response?: { status?: number; data?: { detail?: unknown } };
        message?: string;
      };
      const status = axiosErr?.response?.status;
      const detail = axiosErr?.response?.data?.detail;
      const detailStr =
        typeof detail === "string"
          ? detail
          : Array.isArray(detail)
            ? detail
                .map((d) =>
                  typeof d === "object" && d !== null && "msg" in d
                    ? (d as { msg: string }).msg
                    : String(d),
                )
                .join(", ")
            : (axiosErr?.message ?? "Unknown error");
      setErrors({
        submit: `[${status ?? "ERR"}] ${detailStr}`,
      });
    }
  };

  const handleClose = () => {
    setForm(EMPTY_FORM);
    setErrors({});
    onClose();
  };

  return (
    <Modal
      open={open}
      onOpenChange={handleClose}
      title={`Add admin to ${schoolName}`}
      titleClassName="font-['Inter'] font-bold"
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
        <Input
          label="Temporary password"
          type="password"
          value={form.password}
          onChange={(e) => setForm({ ...form, password: e.target.value })}
          error={errors.password}
          placeholder="Min. 8 characters"
        />

        <p className="text-xs text-role-admin-muted">
          The admin will be prompted to change their password on first login.
        </p>

        {errors.submit && (
          <p className="text-xs text-brand-red">{errors.submit}</p>
        )}

        <div className="flex justify-end gap-3 pt-2">
          <Button type="button" variant="secondary" onClick={handleClose}>
            Cancel
          </Button>
          <Button type="submit" loading={create.isPending}>
            Create admin
          </Button>
        </div>
      </form>
    </Modal>
  );
}
