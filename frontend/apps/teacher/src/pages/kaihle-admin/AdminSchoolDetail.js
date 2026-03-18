import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useState } from "react";
import { useParams, Link } from "react-router-dom";
import { AdminLayout } from "@kaihle/ui";
import { Card, Badge, Button, Skeleton } from "@kaihle/ui";
import { useAdminSchool, useSchoolAnalytics } from "../../hooks/useKaihleAdmin";
import { AdminExtendTrialModal } from "./AdminExtendTrialModal";
import { ArrowLeft, Users, GraduationCap, ClipboardCheck, TrendingUp, Calendar } from "lucide-react";
function getDaysRemaining(trialEndDate) {
    if (!trialEndDate)
        return null;
    const end = new Date(trialEndDate);
    const now = new Date();
    const diff = Math.ceil((end.getTime() - now.getTime()) / (1000 * 60 * 60 * 24));
    return diff > 0 ? diff : 0;
}
function InfoSection({ school }) {
    const statusVariant = school.subscription_status === "ACTIVE" ? "success" :
        school.subscription_status === "TRIAL" ? "warning" : "danger";
    const planVariant = school.plan_tier === "GROWTH" || school.plan_tier === "SCALE" ? "success" : "neutral";
    return (_jsxs(Card, { className: "bg-white border border-role-admin-border", children: [_jsxs("div", { className: "flex items-center justify-between mb-6", children: [_jsx("h3", { className: "text-sm font-bold text-role-admin-ink", children: "School info" }), _jsx(Badge, { variant: statusVariant, children: school.subscription_status })] }), _jsxs("div", { className: "grid grid-cols-2 gap-6", children: [_jsxs("div", { children: [_jsx("p", { className: "text-xs font-bold uppercase tracking-widest text-role-admin-muted mb-1", children: "Name" }), _jsx("p", { className: "text-sm font-semibold text-role-admin-ink", children: school.name })] }), _jsxs("div", { children: [_jsx("p", { className: "text-xs font-bold uppercase tracking-widest text-role-admin-muted mb-1", children: "Slug" }), _jsx("p", { className: "text-sm text-role-admin-subtle", children: school.slug })] }), _jsxs("div", { children: [_jsx("p", { className: "text-xs font-bold uppercase tracking-widest text-role-admin-muted mb-1", children: "Country" }), _jsx("p", { className: "text-sm text-role-admin-subtle", children: school.country || "—" })] }), _jsxs("div", { children: [_jsx("p", { className: "text-xs font-bold uppercase tracking-widest text-role-admin-muted mb-1", children: "City" }), _jsx("p", { className: "text-sm text-role-admin-subtle", children: school.city || "—" })] }), _jsxs("div", { children: [_jsx("p", { className: "text-xs font-bold uppercase tracking-widest text-role-admin-muted mb-1", children: "Timezone" }), _jsx("p", { className: "text-sm text-role-admin-subtle", children: school.timezone })] }), _jsxs("div", { children: [_jsx("p", { className: "text-xs font-bold uppercase tracking-widest text-role-admin-muted mb-1", children: "Plan" }), _jsx("div", { className: "flex items-center gap-2", children: _jsx(Badge, { variant: planVariant, children: school.plan_tier }) })] })] })] }));
}
function TrialSection({ school, onExtend }) {
    const daysRemaining = getDaysRemaining(school.trial_end_date);
    if (school.subscription_status !== "TRIAL" || !school.trial_end_date) {
        return null;
    }
    return (_jsx(Card, { className: "bg-brand-amber-light border border-brand-gold-mid", children: _jsxs("div", { className: "flex items-center justify-between", children: [_jsxs("div", { className: "flex items-center gap-3", children: [_jsx(Calendar, { className: "w-5 h-5 text-brand-amber" }), _jsxs("div", { children: [_jsxs("p", { className: "text-sm font-semibold text-brand-amber-dark", children: ["Trial expires: ", new Date(school.trial_end_date).toLocaleDateString()] }), _jsxs("p", { className: "text-xs text-brand-amber-dark", children: [daysRemaining, " days remaining"] })] })] }), _jsx(Button, { variant: "secondary", size: "sm", onClick: onExtend, children: "Extend trial" })] }) }));
}
function StatsSection({ analytics, loading }) {
    if (loading) {
        return (_jsx(Card, { className: "bg-white border border-role-admin-border", children: _jsx("div", { className: "grid grid-cols-4 gap-4", children: [...Array(4)].map((_, i) => (_jsxs("div", { className: "text-center", children: [_jsx(Skeleton, { className: "h-8 w-8 rounded-full mx-auto mb-2" }), _jsx(Skeleton, { className: "h-4 w-16 mx-auto" }), _jsx(Skeleton, { className: "h-3 w-12 mx-auto mt-1" })] }, i))) }) }));
    }
    return (_jsxs(Card, { className: "bg-white border border-role-admin-border", children: [_jsx("h3", { className: "text-sm font-bold text-role-admin-ink mb-6", children: "Summary stats" }), _jsxs("div", { className: "grid grid-cols-4 gap-4", children: [_jsxs("div", { className: "text-center", children: [_jsx("div", { className: "w-10 h-10 rounded-full bg-brand-light flex items-center justify-center mx-auto mb-2", children: _jsx(Users, { className: "w-5 h-5 text-brand-primary" }) }), _jsx("p", { className: "text-xl font-bold text-role-admin-ink", children: analytics?.teachers_count ?? 0 }), _jsx("p", { className: "text-xs text-role-admin-muted", children: "Teachers" })] }), _jsxs("div", { className: "text-center", children: [_jsx("div", { className: "w-10 h-10 rounded-full bg-brand-light flex items-center justify-center mx-auto mb-2", children: _jsx(GraduationCap, { className: "w-5 h-5 text-brand-primary" }) }), _jsx("p", { className: "text-xl font-bold text-role-admin-ink", children: analytics?.students_count ?? 0 }), _jsx("p", { className: "text-xs text-role-admin-muted", children: "Students" })] }), _jsxs("div", { className: "text-center", children: [_jsx("div", { className: "w-10 h-10 rounded-full bg-brand-light flex items-center justify-center mx-auto mb-2", children: _jsx(ClipboardCheck, { className: "w-5 h-5 text-brand-primary" }) }), _jsx("p", { className: "text-xl font-bold text-role-admin-ink", children: analytics?.assessments_completed ?? 0 }), _jsx("p", { className: "text-xs text-role-admin-muted", children: "Assessments" })] }), _jsxs("div", { className: "text-center", children: [_jsx("div", { className: "w-10 h-10 rounded-full bg-brand-light flex items-center justify-center mx-auto mb-2", children: _jsx(TrendingUp, { className: "w-5 h-5 text-brand-primary" }) }), _jsxs("p", { className: "text-xl font-bold text-role-admin-ink", children: [analytics?.avg_mastery != null ? Math.round(analytics.avg_mastery * 100) : 0, "%"] }), _jsx("p", { className: "text-xs text-role-admin-muted", children: "Avg mastery" })] })] })] }));
}
export function AdminSchoolDetail() {
    const { schoolId } = useParams();
    const [showExtendModal, setShowExtendModal] = useState(false);
    const { data: school, isLoading: schoolLoading } = useAdminSchool(schoolId);
    const { data: analytics, isLoading: analyticsLoading } = useSchoolAnalytics(schoolId);
    if (schoolLoading || !school) {
        return (_jsx(AdminLayout, { pageTitle: "Loading...", children: _jsxs("div", { className: "space-y-6", children: [_jsxs(Link, { to: "/kaihle-admin/schools", className: "inline-flex items-center gap-2 text-sm text-role-admin-subtle hover:text-role-admin-ink", children: [_jsx(ArrowLeft, { className: "w-4 h-4" }), "Back to schools"] }), _jsx(Skeleton, { className: "h-48 w-full" }), _jsx(Skeleton, { className: "h-32 w-full" })] }) }));
    }
    return (_jsxs(AdminLayout, { pageTitle: school.name, children: [_jsxs("div", { className: "space-y-6", children: [_jsxs(Link, { to: "/kaihle-admin/schools", className: "inline-flex items-center gap-2 text-sm text-role-admin-subtle hover:text-role-admin-ink", children: [_jsx(ArrowLeft, { className: "w-4 h-4" }), "Back to schools"] }), _jsx(InfoSection, { school: school }), school.subscription_status === "TRIAL" && (_jsx(TrialSection, { school: school, onExtend: () => setShowExtendModal(true) })), _jsx(StatsSection, { analytics: analytics, loading: analyticsLoading })] }), showExtendModal && schoolId && (_jsx(AdminExtendTrialModal, { schoolId: schoolId, schoolName: school.name, currentTrialEnd: school.trial_end_date, onClose: () => setShowExtendModal(false) }))] }));
}
