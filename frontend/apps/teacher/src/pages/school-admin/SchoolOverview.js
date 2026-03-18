import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { Link } from "react-router-dom";
import { DashboardLayout } from "@kaihle/ui";
import { Card } from "@kaihle/ui";
import { Button } from "@kaihle/ui";
import { Users, GraduationCap, TrendingUp, Plus } from "lucide-react";
import { useSchoolAnalytics, useSchoolClasses, } from "../../hooks/useSchoolAdmin";
export function SchoolOverview() {
    const { data: analytics, isLoading: analyticsLoading } = useSchoolAnalytics();
    const { data: classes, isLoading: classesLoading } = useSchoolClasses();
    const kpis = [
        {
            label: "Teachers",
            value: analytics?.teacher_count ?? 0,
            icon: Users,
            color: "text-brand-primary",
        },
        {
            label: "Students",
            value: analytics?.student_count ?? 0,
            icon: GraduationCap,
            color: "text-brand-primary",
        },
        {
            label: "Onboarding",
            value: `${analytics?.onboarding_percentage ?? 0}%`,
            icon: TrendingUp,
            color: "text-brand-green",
        },
    ];
    return (_jsx(DashboardLayout, { variant: "school-admin", pageTitle: "Overview", pageSubtitle: "Welcome back! Here's what's happening at your school.", children: _jsxs("div", { className: "space-y-6", children: [_jsxs("section", { children: [_jsx("h2", { className: "text-lg font-display font-bold text-brand-ink mb-4", children: "Quick stats" }), _jsx("div", { className: "grid grid-cols-1 md:grid-cols-3 gap-4", children: kpis.map((kpi) => (_jsx(Card, { variant: "default", className: "bg-white border-role-school-border", children: _jsxs("div", { className: "flex items-center justify-between", children: [_jsxs("div", { children: [_jsx("p", { className: "text-sm text-brand-body", children: kpi.label }), _jsx("p", { className: "text-3xl font-display font-bold text-brand-ink mt-1", children: analyticsLoading ? "..." : kpi.value })] }), _jsx("div", { className: `p-3 rounded-full bg-brand-light ${kpi.color}`, children: _jsx(kpi.icon, { className: "w-6 h-6" }) })] }) }, kpi.label))) })] }), _jsxs("section", { children: [_jsxs("div", { className: "flex items-center justify-between mb-4", children: [_jsx("h2", { className: "text-lg font-display font-bold text-brand-ink", children: "Classes" }), _jsx(Link, { to: "/school/classes", children: _jsxs(Button, { variant: "primary", size: "sm", children: [_jsx(Plus, { className: "w-4 h-4 mr-1" }), "Create class"] }) })] }), _jsx(Card, { variant: "default", className: "bg-white border-role-school-border overflow-hidden", children: classesLoading ? (_jsx("div", { className: "p-8 text-center text-brand-muted", children: "Loading..." })) : classes && classes.length > 0 ? (_jsxs("div", { className: "overflow-x-auto", children: [_jsxs("table", { className: "w-full", children: [_jsx("thead", { children: _jsxs("tr", { className: "border-b border-brand-border text-left", children: [_jsx("th", { className: "py-3 px-4 text-xs font-bold uppercase text-brand-muted", children: "Class" }), _jsx("th", { className: "py-3 px-4 text-xs font-bold uppercase text-brand-muted", children: "Teacher" }), _jsx("th", { className: "py-3 px-4 text-xs font-bold uppercase text-brand-muted", children: "Students" })] }) }), _jsx("tbody", { children: classes.slice(0, 10).map((cls) => (_jsxs("tr", { className: "border-b border-brand-border-soft last:border-0 hover:bg-brand-light/30", children: [_jsx("td", { className: "py-3 px-4 text-sm font-medium text-brand-ink", children: cls.name }), _jsx("td", { className: "py-3 px-4 text-sm text-brand-body", children: cls.teacher_name || "Unassigned" }), _jsx("td", { className: "py-3 px-4 text-sm text-brand-body", children: cls.student_count })] }, cls.id))) })] }), classes.length > 10 && (_jsx("div", { className: "p-3 text-center border-t border-brand-border", children: _jsxs(Link, { to: "/school/classes", className: "text-sm text-brand-primary hover:underline", children: ["View all ", classes.length, " classes \u2192"] }) }))] })) : (_jsx("div", { className: "p-8 text-center text-brand-muted", children: "No classes yet. Create your first class to get started." })) })] }), _jsxs("section", { children: [_jsx("h2", { className: "text-lg font-display font-bold text-brand-ink mb-4", children: "Onboarding progress" }), _jsxs(Card, { variant: "highlighted", className: "bg-brand-light border-role-school-border", children: [_jsxs("div", { className: "flex items-center justify-between mb-2", children: [_jsxs("span", { className: "text-sm text-brand-body", children: [analytics?.onboarded_students ?? 0, " of", " ", analytics?.total_students ?? 0, " students fully onboarded"] }), _jsxs("span", { className: "text-sm font-bold text-brand-primary", children: [analytics?.onboarding_percentage ?? 0, "%"] })] }), _jsx("div", { className: "w-full bg-white rounded-full h-3", children: _jsx("div", { className: "bg-brand-primary h-3 rounded-full transition-all duration-500", style: { width: `${analytics?.onboarding_percentage ?? 0}%` }, role: "progressbar", "aria-valuenow": analytics?.onboarding_percentage ?? 0, "aria-valuemin": 0, "aria-valuemax": 100 }) }), _jsx("div", { className: "mt-4 text-right", children: _jsx(Link, { to: "/admin/analytics", className: "text-sm text-brand-primary hover:underline font-medium", children: "View analytics \u2192" }) })] })] })] }) }));
}
