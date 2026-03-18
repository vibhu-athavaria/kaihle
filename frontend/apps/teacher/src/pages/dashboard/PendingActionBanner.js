import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { Link } from "react-router-dom";
import { AlertTriangle } from "lucide-react";
function getActionMessage(action) {
    switch (action.type) {
        case "study-plan":
            return `${action.studentCount} student${action.studentCount !== 1 ? "s" : ""} need study plans in ${action.className}`;
        case "assessment-review":
            return `${action.studentCount} student${action.studentCount !== 1 ? "s" : ""} completed ${action.assessmentName} — view results`;
        case "no-assessments":
            return `No assessments yet for ${action.className} — create one to see gaps`;
    }
}
function getActionLink(action) {
    switch (action.type) {
        case "study-plan":
            return `/teacher/classes/${action.classId}/gap-map`;
        case "assessment-review":
            return `/teacher/classes/${action.classId}/assessments`;
        case "no-assessments":
            return `/teacher/classes/${action.classId}/assessments`;
    }
}
export function PendingActionBanner({ action }) {
    return (_jsxs("div", { className: "bg-brand-gold-light border border-brand-gold-mid rounded-xl p-4 flex items-center justify-between", children: [_jsxs("div", { className: "flex items-center gap-3", children: [_jsx(AlertTriangle, { className: "w-5 h-5 text-brand-gold" }), _jsx("span", { className: "text-sm font-medium text-brand-ink", children: getActionMessage(action) })] }), _jsx(Link, { to: getActionLink(action), className: "text-sm font-semibold text-brand-gold hover:text-brand-gold-dark", children: "Go \u2192" })] }));
}
