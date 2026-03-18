import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { Link } from "react-router-dom";
import { getMasteryStyle, scoreToPercent } from "@kaihle/types";
const subjectColorMap = {
    Mathematics: "bg-brand-blue",
    Science: "bg-brand-green",
    English: "bg-brand-amber",
    History: "bg-brand-red",
    Art: "bg-brand-purple",
    Music: "bg-brand-pink",
    default: "bg-brand-muted",
};
function getSubjectColor(subjectName) {
    return subjectColorMap[subjectName] || subjectColorMap.default;
}
export function ClassCard({ classId, className, subjectName, gradeName, studentCount, avgMastery, }) {
    const { textClass, dotClass, label } = getMasteryStyle(avgMastery);
    const displayPct = scoreToPercent(avgMastery);
    const subjectColor = getSubjectColor(subjectName);
    return (_jsxs("div", { className: "bg-white rounded-2xl border border-role-teacher-border p-5 hover:-translate-y-0.5 hover:shadow-card-hover transition-all", children: [_jsxs("div", { className: "flex items-start justify-between mb-3", children: [_jsxs("div", { className: "flex items-center gap-3", children: [_jsx("div", { className: `w-3 h-3 rounded-full ${subjectColor}` }), _jsx("span", { className: "font-display font-semibold text-brand-ink", children: className })] }), _jsx("span", { className: "px-2 py-0.5 bg-gray-100 text-xs font-medium text-brand-muted rounded-full", children: gradeName })] }), _jsxs("div", { className: "mb-3", children: [_jsxs("div", { className: "text-xs text-role-teacher-muted mb-1", children: [studentCount, " student", studentCount !== 1 ? "s" : ""] }), _jsxs("div", { className: "flex items-center gap-2", children: [_jsx("span", { className: `w-2 h-2 rounded-full ${dotClass}` }), _jsx("span", { className: `text-sm font-semibold ${textClass}`, children: displayPct }), _jsx("span", { className: "text-xs text-brand-muted", children: label })] })] }), _jsxs("div", { className: "border-t border-brand-border pt-3 flex gap-4", children: [_jsx(Link, { to: `/teacher/classes/${classId}/gap-map`, className: "text-sm font-semibold text-brand-body hover:text-brand-primary", children: "Gap Map \u2192" }), _jsx(Link, { to: `/teacher/classes/${classId}/assessments`, className: "text-sm font-semibold text-brand-body hover:text-brand-primary", children: "Assessment \u2192" })] })] }));
}
export function ClassCardSkeleton() {
    return (_jsxs("div", { className: "bg-white rounded-2xl border border-role-teacher-border p-5 animate-pulse", children: [_jsxs("div", { className: "flex items-start justify-between mb-3", children: [_jsxs("div", { className: "flex items-center gap-3", children: [_jsx("div", { className: "w-3 h-3 rounded-full bg-gray-200" }), _jsx("div", { className: "h-5 w-24 bg-gray-200 rounded" })] }), _jsx("div", { className: "h-5 w-12 bg-gray-200 rounded-full" })] }), _jsxs("div", { className: "mb-3", children: [_jsx("div", { className: "h-3 w-16 bg-gray-200 rounded mb-2" }), _jsx("div", { className: "h-4 w-20 bg-gray-200 rounded" })] }), _jsxs("div", { className: "border-t border-brand-border pt-3 flex gap-4", children: [_jsx("div", { className: "h-4 w-16 bg-gray-200 rounded" }), _jsx("div", { className: "h-4 w-20 bg-gray-200 rounded" })] })] }));
}
