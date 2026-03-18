import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
const emojiMap = {
    assessment: "📝",
    "study-plan-ready": "📚",
    "study-plan-progress": "📈",
    "weakest-area": "🎯",
};
export function NextStepCard({ type, title, subtitle, actionLabel, onAction, }) {
    const emoji = emojiMap[type];
    return (_jsxs("div", { className: "bg-white rounded-2xl border border-role-student-border p-4 flex items-center justify-between", children: [_jsxs("div", { className: "flex items-center gap-3", children: [_jsx("span", { className: "text-2xl", role: "img", "aria-label": type, children: emoji }), _jsxs("div", { children: [_jsx("div", { className: "font-semibold text-brand-ink", children: title }), _jsx("div", { className: "text-xs text-brand-muted", children: subtitle })] })] }), _jsx("button", { onClick: onAction, className: "text-sm font-bold text-brand-primary whitespace-nowrap hover:underline", children: actionLabel })] }));
}
export function EmptyNextSteps({ message = "You're all caught up! Check back after your next assessment.", }) {
    return (_jsx("div", { className: "bg-brand-light rounded-2xl p-4 text-center", children: _jsx("p", { className: "text-sm text-brand-body", children: message }) }));
}
