import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useState } from "react";
import { Button } from "@kaihle/ui";
import { Input } from "@kaihle/ui";
import { X } from "lucide-react";
const roleOptions = [
    { value: "TEACHER", label: "Teacher" },
    { value: "STUDENT", label: "Student" },
    { value: "PARENT", label: "Parent" },
];
export function InviteUserModal({ isOpen, onClose, onInvite, defaultRole = "TEACHER", }) {
    const [firstName, setFirstName] = useState("");
    const [lastName, setLastName] = useState("");
    const [email, setEmail] = useState("");
    const [role, setRole] = useState(defaultRole);
    const [errors, setErrors] = useState({});
    const [isSubmitting, setIsSubmitting] = useState(false);
    if (!isOpen)
        return null;
    const validate = () => {
        const newErrors = {};
        if (!firstName.trim()) {
            newErrors.firstName = "First name is required";
        }
        if (!lastName.trim()) {
            newErrors.lastName = "Last name is required";
        }
        if (!email.trim()) {
            newErrors.email = "Email is required";
        }
        else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
            newErrors.email = "Enter a valid email address";
        }
        setErrors(newErrors);
        return Object.keys(newErrors).length === 0;
    };
    const handleSubmit = async (e) => {
        e.preventDefault();
        if (!validate())
            return;
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
        }
        catch {
            // Error handling done by caller
        }
        finally {
            setIsSubmitting(false);
        }
    };
    const getTitle = () => {
        switch (role) {
            case "TEACHER":
                return "Invite a teacher";
            case "STUDENT":
                return "Invite a student";
            case "PARENT":
                return "Invite a parent";
        }
    };
    return (_jsxs("div", { className: "fixed inset-0 z-50 flex items-center justify-center", children: [_jsx("div", { className: "absolute inset-0 bg-black/40", onClick: onClose, "aria-hidden": "true" }), _jsxs("div", { className: "relative bg-white rounded-2xl border border-brand-border shadow-xl p-6 w-full max-w-md mx-4 animate-in fade-in zoom-in-95 duration-200", role: "dialog", "aria-modal": "true", "aria-labelledby": "modal-title", children: [_jsx("button", { onClick: onClose, className: "absolute top-4 right-4 p-1 text-brand-muted hover:text-brand-ink rounded-full hover:bg-gray-100", "aria-label": "Close", children: _jsx(X, { className: "w-5 h-5" }) }), _jsx("h2", { id: "modal-title", className: "text-xl font-display font-bold text-brand-ink mb-6", children: getTitle() }), _jsxs("form", { onSubmit: handleSubmit, className: "space-y-4", children: [_jsx("div", { children: _jsx(Input, { id: "firstName", label: "First name", type: "text", value: firstName, onChange: (e) => setFirstName(e.target.value), placeholder: "Enter first name", error: errors.firstName }) }), _jsx("div", { children: _jsx(Input, { id: "lastName", label: "Last name", type: "text", value: lastName, onChange: (e) => setLastName(e.target.value), placeholder: "Enter last name", error: errors.lastName }) }), _jsx("div", { children: _jsx(Input, { id: "email", label: "Email address", type: "email", value: email, onChange: (e) => setEmail(e.target.value), placeholder: "Enter email address", error: errors.email }) }), _jsxs("div", { children: [_jsx("label", { htmlFor: "role", className: "block text-sm font-semibold text-brand-ink mb-1.5", children: "Role" }), _jsx("select", { id: "role", value: role, onChange: (e) => setRole(e.target.value), className: "w-full px-4 py-2.5 rounded-xl border border-brand-border bg-white text-brand-ink font-sans text-sm focus:outline-none focus:ring-2 focus:ring-brand-primary/30 focus:border-brand-primary", children: roleOptions.map((opt) => (_jsx("option", { value: opt.value, children: opt.label }, opt.value))) })] }), _jsxs("div", { className: "flex gap-3 pt-4", children: [_jsx(Button, { type: "button", variant: "secondary", onClick: onClose, className: "flex-1", children: "Cancel" }), _jsx(Button, { type: "submit", variant: "primary", loading: isSubmitting, className: "flex-1", children: "Send invite \u2192" })] })] })] })] }));
}
