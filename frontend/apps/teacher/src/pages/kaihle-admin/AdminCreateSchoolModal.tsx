import { useState } from "react";
import { Card, Button, Input } from "@kaihle/ui";
import { useCreateSchool } from "../../hooks/useKaihleAdmin";

const TIMEZONES = [
  { value: "Asia/Makassar", label: "Asia/Makassar (WITA)" },
  { value: "Asia/Jakarta", label: "Asia/Jakarta (WIB)" },
  { value: "Asia/Jayapura", label: "Asia/Jayapura (WIT)" },
  { value: "Asia/Singapore", label: "Asia/Singapore (SGT)" },
  { value: "UTC", label: "UTC" },
];

const PLAN_TIERS = [
  { value: "TRIAL", label: "Trial" },
  { value: "STARTER", label: "Starter" },
  { value: "GROWTH", label: "Growth" },
  { value: "SCALE", label: "Scale" },
];

function deriveSlug(name: string): string {
  return name
    .toLowerCase()
    .replace(/[^a-z0-9\s-]/g, "")
    .replace(/\s+/g, "-")
    .replace(/-+/g, "-")
    .trim();
}

function validateSlug(slug: string): string | null {
  if (!slug) return "Slug is required";
  if (!/^[a-z0-9-]+$/.test(slug))
    return "Slug can only contain lowercase letters, numbers, and hyphens";
  if (slug.startsWith("-") || slug.endsWith("-"))
    return "Slug cannot start or end with a hyphen";
  return null;
}

function validateEmail(email: string): string | null {
  if (!email) return "Admin email is required";
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  if (!emailRegex.test(email)) return "Please enter a valid email address";
  return null;
}

export function AdminCreateSchoolModal({ onClose }: { onClose: () => void }) {
  const createSchool = useCreateSchool();
  const [formData, setFormData] = useState({
    name: "",
    slug: "",
    country: "",
    city: "",
    timezone: "Asia/Makassar",
    plan_tier: "TRIAL" as const,
    admin_email: "",
    admin_first_name: "",
    admin_last_name: "",
  });
  const [errors, setErrors] = useState<Record<string, string>>({});

  const handleNameChange = (name: string) => {
    const slug = formData.slug || deriveSlug(name);
    setFormData({ ...formData, name, slug });
    if (errors.name) setErrors({ ...errors, name: "" });
  };

  const handleSlugChange = (slug: string) => {
    setFormData({ ...formData, slug });
    const slugError = validateSlug(slug);
    if (slugError) setErrors({ ...errors, slug: slugError });
    else if (errors.slug) setErrors({ ...errors, slug: "" });
  };

  const handleEmailChange = (email: string) => {
    setFormData({ ...formData, admin_email: email });
    if (errors.admin_email) setErrors({ ...errors, admin_email: "" });
  };

  const validate = (): boolean => {
    const newErrors: Record<string, string> = {};
    if (!formData.name.trim()) newErrors.name = "School name is required";
    if (!formData.slug.trim()) newErrors.slug = "Slug is required";
    else {
      const slugError = validateSlug(formData.slug);
      if (slugError) newErrors.slug = slugError;
    }
    const emailError = validateEmail(formData.admin_email);
    if (emailError) newErrors.admin_email = emailError;
    if (!formData.admin_first_name.trim())
      newErrors.admin_first_name = "First name is required";
    if (!formData.admin_last_name.trim())
      newErrors.admin_last_name = "Last name is required";
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!validate()) return;

    try {
      await createSchool.mutateAsync(formData);
      onClose();
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : "Unknown error";
      console.error("Failed to create school:", errorMessage);
      setErrors({ submit: `Failed to create school: ${errorMessage}` });
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <Card className="w-full max-w-lg bg-white border border-role-admin-border max-h-[90vh] overflow-y-auto">
        <div className="p-6">
          <h2 className="text-xl font-bold text-role-admin-ink mb-6">
            Create new school
          </h2>
          <form onSubmit={handleSubmit} className="space-y-4">
            <Input
              label="School name"
              value={formData.name}
              onChange={(e) => handleNameChange(e.target.value)}
              error={errors.name}
              placeholder="e.g. Bali Coding School"
            />

            <Input
              label="Slug"
              value={formData.slug}
              onChange={(e) => handleSlugChange(e.target.value)}
              error={errors.slug}
              placeholder="e.g. bali-coding-school"
              hint="URL-friendly identifier (lowercase, hyphens only)"
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
                className="w-full bg-white border border-brand-border rounded-xl px-4 py-2.5 text-sm text-role-admin-ink focus:outline-none focus:ring-2 focus:ring-brand-primary/30"
              >
                {TIMEZONES.map((tz) => (
                  <option key={tz.value} value={tz.value}>
                    {tz.label}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-sm font-semibold text-role-admin-ink mb-1.5">
                Plan tier
              </label>
              <select
                value={formData.plan_tier}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    plan_tier: e.target.value as typeof formData.plan_tier,
                  })
                }
                className="w-full bg-white border border-brand-border rounded-xl px-4 py-2.5 text-sm text-role-admin-ink focus:outline-none focus:ring-2 focus:ring-brand-primary/30"
              >
                {PLAN_TIERS.map((plan) => (
                  <option key={plan.value} value={plan.value}>
                    {plan.label}
                  </option>
                ))}
              </select>
            </div>

            <div className="pt-4 border-t border-role-admin-border">
              <p className="text-xs font-bold uppercase tracking-widest text-role-admin-muted mb-4">
                School Admin
              </p>
              <Input
                label="Admin email"
                type="email"
                value={formData.admin_email}
                onChange={(e) => handleEmailChange(e.target.value)}
                error={errors.admin_email}
                placeholder="admin@school.com"
              />
              <div className="grid grid-cols-2 gap-4 mt-4">
                <Input
                  label="Admin first name"
                  value={formData.admin_first_name}
                  onChange={(e) =>
                    setFormData({
                      ...formData,
                      admin_first_name: e.target.value,
                    })
                  }
                  error={errors.admin_first_name}
                  placeholder="John"
                />
                <Input
                  label="Admin last name"
                  value={formData.admin_last_name}
                  onChange={(e) =>
                    setFormData({
                      ...formData,
                      admin_last_name: e.target.value,
                    })
                  }
                  error={errors.admin_last_name}
                  placeholder="Doe"
                />
              </div>
            </div>

            {errors.submit && (
              <p className="text-sm text-brand-red">{errors.submit}</p>
            )}

            <div className="flex justify-end gap-3 pt-4">
              <Button type="button" variant="secondary" onClick={onClose}>
                Cancel
              </Button>
              <Button type="submit" loading={createSchool.isPending}>
                Create school
              </Button>
            </div>
          </form>
        </div>
      </Card>
    </div>
  );
}
