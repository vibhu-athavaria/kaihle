import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
export function StreakBadge({ days }) {
    if (days <= 1) {
        return null;
    }
    return (_jsxs("div", { className: "inline-flex items-center gap-1.5 bg-brand-gold-light px-3 py-1.5 rounded-full", children: [_jsx("span", { role: "img", "aria-label": "fire", children: "\uD83D\uDD25" }), _jsxs("span", { className: "text-sm font-bold text-brand-gold-dark", children: [days, " day", days !== 1 ? "s" : ""] })] }));
}
