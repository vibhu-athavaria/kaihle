import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useState } from "react";
import { Card, Button, Input } from "@kaihle/ui";
import { useExtendTrial } from "../../hooks/useKaihleAdmin";
const extensionOptions = [
    { days: 7, label: "7 days" },
    { days: 14, label: "14 days" },
    { days: 30, label: "30 days" },
];
export function AdminExtendTrialModal({ schoolId, schoolName: _schoolName, currentTrialEnd, onClose, }) {
    const extendTrial = useExtendTrial();
    const [selectedDays, setSelectedDays] = useState(14);
    const [reason, setReason] = useState("");
    const [error, setError] = useState("");
    const handleSubmit = async (e) => {
        e.preventDefault();
        if (!reason.trim()) {
            setError("Reason is required");
            return;
        }
        try {
            await extendTrial.mutateAsync({
                id: schoolId,
                data: { days: selectedDays, reason },
            });
            onClose();
        }
        catch (err) {
            setError("Failed to extend trial. Please try again.");
        }
    };
    return (_jsx("div", { className: "fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4", children: _jsx(Card, { className: "w-full max-w-md bg-white border border-role-admin-border", children: _jsxs("div", { className: "p-6", children: [_jsx("h2", { className: "text-xl font-bold text-role-admin-ink mb-2", children: "Extend trial" }), _jsx("p", { className: "text-sm text-role-admin-subtle mb-6", children: currentTrialEnd && (_jsxs("span", { children: ["Current trial ends: ", new Date(currentTrialEnd).toLocaleDateString()] })) }), _jsxs("form", { onSubmit: handleSubmit, className: "space-y-6", children: [_jsxs("div", { children: [_jsx("label", { className: "block text-sm font-semibold text-role-admin-ink mb-3", children: "Extension period" }), _jsx("div", { className: "flex gap-2", children: extensionOptions.map((option) => (_jsx("button", { type: "button", onClick: () => setSelectedDays(option.days), className: [
                                                "flex-1 py-2.5 px-4 rounded-lg text-sm font-semibold transition-colors",
                                                selectedDays === option.days
                                                    ? "bg-brand-primary text-white"
                                                    : "bg-gray-100 text-role-admin-subtle hover:bg-gray-200",
                                            ].join(" "), children: option.label }, option.days))) })] }), _jsx(Input, { label: "Reason", value: reason, onChange: (e) => {
                                    setReason(e.target.value);
                                    if (error)
                                        setError("");
                                }, error: error, placeholder: "Reason for extending trial (required)", hint: "Stored for audit purposes" }), _jsxs("div", { className: "flex justify-end gap-3 pt-2", children: [_jsx(Button, { type: "button", variant: "secondary", onClick: onClose, children: "Cancel" }), _jsx(Button, { type: "submit", loading: extendTrial.isPending, children: "Extend trial" })] })] })] }) }) }));
}
