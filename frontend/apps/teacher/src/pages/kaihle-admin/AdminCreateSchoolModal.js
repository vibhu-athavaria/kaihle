import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
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
function deriveSlug(name) {
    return name
        .toLowerCase()
        .replace(/[^a-z0-9\s-]/g, "")
        .replace(/\s+/g, "-")
        .replace(/-+/g, "-")
        .trim();
}
function validateSlug(slug) {
    if (!slug)
        return "Slug is required";
    if (!/^[a-z0-9-]+$/.test(slug))
        return "Slug can only contain lowercase letters, numbers, and hyphens";
    if (slug.startsWith("-") || slug.endsWith("-"))
        return "Slug cannot start or end with a hyphen";
    return null;
}
export function AdminCreateSchoolModal({ onClose }) {
    const createSchool = useCreateSchool();
    const [formData, setFormData] = useState({
        name: "",
        slug: "",
        country: "",
        city: "",
        timezone: "Asia/Makassar",
        plan_tier: "TRIAL",
        admin_email: "",
        admin_first_name: "",
        admin_last_name: "",
    });
    const [errors, setErrors] = useState({});
    const handleNameChange = (name) => {
        const slug = formData.slug || deriveSlug(name);
        setFormData({ ...formData, name, slug });
        if (errors.name)
            setErrors({ ...errors, name: "" });
    };
    const handleSlugChange = (slug) => {
        setFormData({ ...formData, slug });
        const slugError = validateSlug(slug);
        if (slugError)
            setErrors({ ...errors, slug: slugError });
        else if (errors.slug)
            setErrors({ ...errors, slug: "" });
    };
    const validate = () => {
        const newErrors = {};
        if (!formData.name.trim())
            newErrors.name = "School name is required";
        if (!formData.slug.trim())
            newErrors.slug = "Slug is required";
        else {
            const slugError = validateSlug(formData.slug);
            if (slugError)
                newErrors.slug = slugError;
        }
        if (!formData.admin_email.trim())
            newErrors.admin_email = "Admin email is required";
        if (!formData.admin_first_name.trim())
            newErrors.admin_first_name = "First name is required";
        if (!formData.admin_last_name.trim())
            newErrors.admin_last_name = "Last name is required";
        setErrors(newErrors);
        return Object.keys(newErrors).length === 0;
    };
    const handleSubmit = async (e) => {
        e.preventDefault();
        if (!validate())
            return;
        try {
            await createSchool.mutateAsync(formData);
            onClose();
        }
        catch (err) {
            setErrors({ submit: "Failed to create school. Please try again." });
        }
    };
    return (_jsx("div", { className: "fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4", children: _jsx(Card, { className: "w-full max-w-lg bg-white border border-role-admin-border max-h-[90vh] overflow-y-auto", children: _jsxs("div", { className: "p-6", children: [_jsx("h2", { className: "text-xl font-bold text-role-admin-ink mb-6", children: "Create new school" }), _jsxs("form", { onSubmit: handleSubmit, className: "space-y-4", children: [_jsx(Input, { label: "School name", value: formData.name, onChange: (e) => handleNameChange(e.target.value), error: errors.name, placeholder: "e.g. Bali Coding School" }), _jsx(Input, { label: "Slug", value: formData.slug, onChange: (e) => handleSlugChange(e.target.value), error: errors.slug, placeholder: "e.g. bali-coding-school", hint: "URL-friendly identifier (lowercase, hyphens only)" }), _jsxs("div", { className: "grid grid-cols-2 gap-4", children: [_jsx(Input, { label: "Country", value: formData.country, onChange: (e) => setFormData({ ...formData, country: e.target.value }), placeholder: "e.g. Indonesia" }), _jsx(Input, { label: "City", value: formData.city, onChange: (e) => setFormData({ ...formData, city: e.target.value }), placeholder: "e.g. Bali" })] }), _jsxs("div", { children: [_jsx("label", { className: "block text-sm font-semibold text-role-admin-ink mb-1.5", children: "Timezone" }), _jsx("select", { value: formData.timezone, onChange: (e) => setFormData({ ...formData, timezone: e.target.value }), className: "w-full bg-white border border-brand-border rounded-xl px-4 py-2.5 text-sm text-role-admin-ink focus:outline-none focus:ring-2 focus:ring-brand-primary/30", children: TIMEZONES.map((tz) => (_jsx("option", { value: tz.value, children: tz.label }, tz.value))) })] }), _jsxs("div", { children: [_jsx("label", { className: "block text-sm font-semibold text-role-admin-ink mb-1.5", children: "Plan tier" }), _jsx("select", { value: formData.plan_tier, onChange: (e) => setFormData({ ...formData, plan_tier: e.target.value }), className: "w-full bg-white border border-brand-border rounded-xl px-4 py-2.5 text-sm text-role-admin-ink focus:outline-none focus:ring-2 focus:ring-brand-primary/30", children: PLAN_TIERS.map((plan) => (_jsx("option", { value: plan.value, children: plan.label }, plan.value))) })] }), _jsxs("div", { className: "pt-4 border-t border-role-admin-border", children: [_jsx("p", { className: "text-xs font-bold uppercase tracking-widest text-role-admin-muted mb-4", children: "School Admin" }), _jsx(Input, { label: "Admin email", type: "email", value: formData.admin_email, onChange: (e) => setFormData({ ...formData, admin_email: e.target.value }), error: errors.admin_email, placeholder: "admin@school.com" }), _jsxs("div", { className: "grid grid-cols-2 gap-4 mt-4", children: [_jsx(Input, { label: "Admin first name", value: formData.admin_first_name, onChange: (e) => setFormData({ ...formData, admin_first_name: e.target.value }), error: errors.admin_first_name, placeholder: "John" }), _jsx(Input, { label: "Admin last name", value: formData.admin_last_name, onChange: (e) => setFormData({ ...formData, admin_last_name: e.target.value }), error: errors.admin_last_name, placeholder: "Doe" })] })] }), errors.submit && (_jsx("p", { className: "text-sm text-brand-red", children: errors.submit })), _jsxs("div", { className: "flex justify-end gap-3 pt-4", children: [_jsx(Button, { type: "button", variant: "secondary", onClick: onClose, children: "Cancel" }), _jsx(Button, { type: "submit", loading: createSchool.isPending, children: "Create school" })] })] })] }) }) }));
}
