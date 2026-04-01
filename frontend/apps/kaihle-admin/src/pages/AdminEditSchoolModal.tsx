import { useState } from "react";
import { Card, Button, Input } from "@kaihle/ui";
import {
  useUpdateSchool,
  useUpdateSchoolAdminPassword,
  School,
} from "../hooks/useKaihleAdmin";

const TIMEZONES = [
  { value: "Asia/Makassar", label: "Asia/Makassar (WITA)" },
  { value: "Asia/Jakarta", label: "Asia/Jakarta (WIB)" },
  { value: "Asia/Jayapura", label: "Asia/Jayapura (WIT)" },
  { value: "Asia/Singapore", label: "Asia/Singapore (SGT)" },
  { value: "UTC", label: "UTC" },
];

interface AdminEditSchoolModalProps {
  school: School;
  onClose: () => void;
}

export function AdminEditSchoolModal({
  school,
  onClose,
}: AdminEditSchoolModalProps) {
  const updateSchool = useUpdateSchool();
  const updatePassword = useUpdateSchoolAdminPassword();

  const [formData, setFormData] = useState({
    name: school.name,
    country: school.country,
    city: school.city,
    timezone: school.timezone,
    is_active: true,
  });

  const [passwordData, setPasswordData] = useState({
    new_password: "",
    confirm_password: "",
  });

  const [errors, setErrors] = useState<Record<string, string>>({});
  const [passwordError, setPasswordError] = useState("");
  const [passwordSuccess, setPasswordSuccess] = useState(false);

  const validateSchoolData = (): boolean => {
    const newErrors: Record<string, string> = {};
    if (!formData.name.trim()) newErrors.name = "School name is required";
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const validatePasswordData = (): boolean => {
    const newErrors: Record<string, string> = {};
    if (!passwordData.new_password) {
      newErrors.new_password = "Password is required";
    } else if (passwordData.new_password.length < 8) {
      newErrors.new_password = "Password must be at least 8 characters";
    }
    if (passwordData.new_password !== passwordData.confirm_password) {
      newErrors.confirm_password = "Passwords do not match";
    }
    setPasswordError("");
    setErrors({ ...errors, ...newErrors });
    return Object.keys(newErrors).length === 0;
  };

  const handleSchoolSave = async () => {
    if (!validateSchoolData()) return;

    try {
      await updateSchool.mutateAsync({
        id: school.id,
        data: formData,
      });
      onClose();
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : "Unknown error";
      setErrors({ submit: `Failed to update school: ${errorMessage}` });
    }
  };

  const handlePasswordSave = async () => {
    if (!validatePasswordData()) return;
    if (!school.admin_user_id) return;

    try {
      await updatePassword.mutateAsync({
        schoolId: school.id,
        userId: school.admin_user_id,
        password: passwordData.new_password,
      });
      setPasswordSuccess(true);
      setPasswordData({ new_password: "", confirm_password: "" });
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : "Unknown error";
      setPasswordError(`Failed to update password: ${errorMessage}`);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <Card className="w-full max-w-lg bg-white border border-role-admin-border max-h-[90vh] overflow-y-auto font-['Inter']">
        <div className="p-6">
          <h2 className="text-xl font-bold text-role-admin-ink mb-6">
            Edit school
          </h2>

          {/* Section A: School Info */}
          <div className="space-y-4">
            <h3 className="text-sm font-semibold text-role-admin-ink">
              School Information
            </h3>

            <Input
              label="School name"
              value={formData.name}
              onChange={(e) =>
                setFormData({ ...formData, name: e.target.value })
              }
              error={errors.name}
            />

            <div className="grid grid-cols-2 gap-4">
              <Input
                label="Country"
                value={formData.country}
                onChange={(e) =>
                  setFormData({ ...formData, country: e.target.value })
                }
                placeholder="e.g. Indonesia"
              />
              <Input
                label="City"
                value={formData.city}
                onChange={(e) =>
                  setFormData({ ...formData, city: e.target.value })
                }
                placeholder="e.g. Bali"
              />
            </div>

            <div>
              <label className="block text-sm font-semibold text-role-admin-ink mb-1.5">
                Timezone
              </label>
              <select
                value={formData.timezone}
                onChange={(e) =>
                  setFormData({ ...formData, timezone: e.target.value })
                }
                className="w-full bg-white border border-brand-border rounded-xl px-4 py-2.5 text-sm text-role-admin-ink focus:outline-none focus:ring-2 focus:ring-brand-primary/30 min-h-[44px]"
              >
                {TIMEZONES.map((tz) => (
                  <option key={tz.value} value={tz.value}>
                    {tz.label}
                  </option>
                ))}
              </select>
            </div>

            <div className="flex items-center gap-2">
              <input
                type="checkbox"
                id="is_active"
                checked={formData.is_active}
                onChange={(e) =>
                  setFormData({ ...formData, is_active: e.target.checked })
                }
                className="w-4 h-4 rounded border-brand-border text-brand-primary focus:ring-brand-primary"
              />
              <label
                htmlFor="is_active"
                className="text-sm text-role-admin-ink"
              >
                Active
              </label>
            </div>

            {errors.submit && (
              <p className="text-sm text-brand-red">{errors.submit}</p>
            )}

            <div className="flex justify-end">
              <Button
                onClick={handleSchoolSave}
                loading={updateSchool.isPending}
                className="min-h-[44px]"
              >
                Save changes
              </Button>
            </div>
          </div>

          {/* Section B: Reset School Admin Password */}
          {school.admin_user_id && (
            <div className="pt-4 border-t border-role-admin-border">
              <h3 className="text-sm font-semibold text-role-admin-ink mb-4">
                Reset School Admin Password
              </h3>

              <div className="space-y-4">
                <Input
                  label="New password"
                  type="password"
                  value={passwordData.new_password}
                  onChange={(e) =>
                    setPasswordData({
                      ...passwordData,
                      new_password: e.target.value,
                    })
                  }
                  error={errors.new_password}
                />

                <Input
                  label="Confirm password"
                  type="password"
                  value={passwordData.confirm_password}
                  onChange={(e) =>
                    setPasswordData({
                      ...passwordData,
                      confirm_password: e.target.value,
                    })
                  }
                  error={errors.confirm_password}
                />

                {passwordError && (
                  <p className="text-sm text-brand-red">{passwordError}</p>
                )}

                {passwordSuccess && (
                  <p className="text-sm text-brand-primary">Password updated</p>
                )}

                <div className="flex justify-end">
                  <Button
                    onClick={handlePasswordSave}
                    loading={updatePassword.isPending}
                    className="min-h-[44px]"
                  >
                    Update password
                  </Button>
                </div>
              </div>
            </div>
          )}

          <div className="flex justify-end pt-4 mt-4">
            <Button
              variant="secondary"
              onClick={onClose}
              className="min-h-[44px]"
            >
              Close
            </Button>
          </div>
        </div>
      </Card>
    </div>
  );
}
