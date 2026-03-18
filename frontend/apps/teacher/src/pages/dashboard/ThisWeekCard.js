import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { Link } from "react-router-dom";
import { BookOpen } from "lucide-react";
export function ThisWeekCard({ lessonPlan }) {
    if (!lessonPlan) {
        return (_jsx("div", { className: "bg-brand-light rounded-xl border border-brand-mid p-4", children: _jsx("p", { className: "text-sm text-brand-body", children: "Lesson plans generate every Monday at 6am. Create assessments first to get started." }) }));
    }
    const displayTopics = lessonPlan.topics.slice(0, 2).join(", ");
    return (_jsxs("div", { className: "bg-brand-light rounded-xl border border-brand-mid p-4 flex items-center justify-between", children: [_jsxs("div", { className: "flex items-center gap-3", children: [_jsx(BookOpen, { className: "w-5 h-5 text-brand-primary" }), _jsxs("div", { children: [_jsxs("div", { className: "text-sm font-semibold text-brand-ink", children: ["Lesson plan ready \u00B7 ", lessonPlan.className] }), _jsxs("div", { className: "text-xs text-brand-muted mt-0.5", children: ["Covers: ", displayTopics] })] })] }), _jsx(Link, { to: `/teacher/classes/${lessonPlan.classId}/lesson-plans`, className: "text-sm font-semibold text-brand-primary hover:text-brand-dark", children: "View plan \u2192" })] }));
}
