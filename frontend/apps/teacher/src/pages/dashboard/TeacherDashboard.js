import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { DashboardLayout } from "@kaihle/ui";
import { Button } from "@kaihle/ui";
import { Plus } from "lucide-react";
import { useTeacherDashboard } from "../../hooks/useTeacherDashboard";
import { ClassCard, ClassCardSkeleton } from "./ClassCard";
import { PendingActionBanner } from "./PendingActionBanner";
import { ThisWeekCard } from "./ThisWeekCard";
import { Link } from "react-router-dom";
import { useAuth } from "@kaihle/auth";
export function TeacherDashboard() {
    const { user } = useAuth();
    const schoolId = user?.school_id || null;
    const { data, isLoading, isError } = useTeacherDashboard(schoolId);
    const greeting = () => {
        const hour = new Date().getHours();
        if (hour < 12)
            return "Good morning";
        if (hour < 18)
            return "Good afternoon";
        return "Good evening";
    };
    const teacherName = user?.email?.split("@")[0] || "Teacher";
    return (_jsxs(DashboardLayout, { variant: "teacher", pageTitle: `${greeting()}, ${teacherName}`, topNavAction: _jsx(Link, { to: "/teacher/assessments/new", children: _jsxs(Button, { variant: "primary", size: "sm", className: "gap-1 bg-brand-gold hover:bg-brand-gold-dark", children: [_jsx(Plus, { className: "w-4 h-4" }), "Assessment"] }) }), children: [isError && (_jsx("div", { className: "text-red-600 p-4 bg-red-50 rounded-lg", children: "Failed to load dashboard. Please try again." })), data.pendingActions.length > 0 && (_jsx("div", { className: "mb-6", children: _jsx(PendingActionBanner, { action: data.pendingActions[0] }) })), _jsxs("div", { className: "mb-6", children: [_jsx("h2", { className: "font-sans text-xs font-bold uppercase tracking-widest text-role-teacher-muted mb-4", children: "My classes" }), _jsx("div", { className: "grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4", children: isLoading
                            ? Array.from({ length: 3 }).map((_, i) => (_jsx(ClassCardSkeleton, {}, i)))
                            : data.classes.map((cls) => (_jsx(ClassCard, { classId: cls.id, className: cls.name, subjectName: cls.subjectName, gradeName: cls.gradeName, studentCount: cls.studentCount, avgMastery: cls.avgMastery, lessonPlanStatus: cls.lessonPlanStatus }, cls.id))) })] }), _jsxs("div", { children: [_jsx("h2", { className: "font-sans text-xs font-bold uppercase tracking-widest text-role-teacher-muted mb-4", children: "This week" }), _jsx(ThisWeekCard, { lessonPlan: data.lessonPlan })] })] }));
}
