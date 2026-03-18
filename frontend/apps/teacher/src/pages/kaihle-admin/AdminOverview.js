import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { Link } from "react-router-dom";
import { AdminLayout } from "@kaihle/ui";
import { Card, Badge, Button, Skeleton } from "@kaihle/ui";
import { usePlatformStats, useAdminSchools, useRecentActivity } from "../../hooks/useKaihleAdmin";
import { TrendingUp, Users, DollarSign, Activity } from "lucide-react";
function KPICard({ icon, label, value, valueColor = "text-role-admin-ink", loading, }) {
    if (loading) {
        return (_jsx(Card, { className: "bg-white border border-role-admin-border", children: _jsxs("div", { className: "flex items-center gap-4", children: [_jsx("div", { className: "w-12 h-12 rounded-xl bg-gray-100 flex items-center justify-center", children: _jsx(Skeleton, { className: "w-6 h-6 rounded" }) }), _jsxs("div", { children: [_jsx(Skeleton, { className: "h-3 w-16 mb-2" }), _jsx(Skeleton, { className: "h-6 w-12" })] })] }) }));
    }
    return (_jsx(Card, { className: "bg-white border border-role-admin-border", children: _jsxs("div", { className: "flex items-center gap-4", children: [_jsx("div", { className: "w-12 h-12 rounded-xl bg-brand-light flex items-center justify-center text-brand-primary", children: icon }), _jsxs("div", { children: [_jsx("p", { className: "text-xs font-bold uppercase tracking-widest text-role-admin-muted", children: label }), _jsx("p", { className: `text-2xl font-bold ${valueColor}`, children: value })] })] }) }));
}
function getTrialBadgeVariant(daysRemaining) {
    if (daysRemaining === null)
        return "neutral";
    if (daysRemaining < 3)
        return "danger";
    if (daysRemaining < 7)
        return "warning";
    return "neutral";
}
function getDaysRemaining(trialEndDate) {
    if (!trialEndDate)
        return null;
    const end = new Date(trialEndDate);
    const now = new Date();
    const diff = Math.ceil((end.getTime() - now.getTime()) / (1000 * 60 * 60 * 24));
    return diff > 0 ? diff : 0;
}
function SchoolStatusTable({ schools, loading }) {
    if (loading) {
        return (_jsx("div", { className: "space-y-3", children: [...Array(4)].map((_, i) => (_jsxs("div", { className: "flex items-center gap-4 p-4 border border-role-admin-border rounded-xl", children: [_jsx(Skeleton, { className: "h-4 w-32" }), _jsx(Skeleton, { className: "h-4 w-20" }), _jsx(Skeleton, { className: "h-4 w-16" }), _jsx(Skeleton, { className: "h-4 w-12" })] }, i))) }));
    }
    return (_jsx("div", { className: "overflow-x-auto", children: _jsxs("table", { className: "w-full", children: [_jsx("thead", { children: _jsxs("tr", { className: "border-b border-role-admin-border", children: [_jsx("th", { className: "text-left py-3 px-4 text-xs font-bold uppercase tracking-widest text-role-admin-muted", children: "Name" }), _jsx("th", { className: "text-left py-3 px-4 text-xs font-bold uppercase tracking-widest text-role-admin-muted", children: "Status" }), _jsx("th", { className: "text-left py-3 px-4 text-xs font-bold uppercase tracking-widest text-role-admin-muted", children: "Plan" }), _jsx("th", { className: "text-left py-3 px-4 text-xs font-bold uppercase tracking-widest text-role-admin-muted", children: "Expiry" })] }) }), _jsx("tbody", { children: schools.map((school) => {
                        const daysRemaining = getDaysRemaining(school.trial_end_date);
                        const badgeVariant = school.subscription_status === "ACTIVE" ? "success" :
                            school.subscription_status === "TRIAL" ? getTrialBadgeVariant(daysRemaining) : "danger";
                        return (_jsxs("tr", { className: "border-b border-role-admin-border hover:bg-gray-50 transition-colors", children: [_jsx("td", { className: "py-3 px-4", children: _jsx(Link, { to: `/kaihle-admin/schools/${school.id}`, className: "text-sm font-semibold text-role-admin-ink hover:text-brand-primary", children: school.name }) }), _jsx("td", { className: "py-3 px-4", children: _jsx(Badge, { variant: badgeVariant, children: school.subscription_status }) }), _jsx("td", { className: "py-3 px-4 text-sm text-role-admin-subtle", children: school.plan_tier }), _jsx("td", { className: "py-3 px-4 text-sm text-role-admin-subtle", children: school.subscription_status === "TRIAL" && school.trial_end_date
                                        ? `${daysRemaining}d`
                                        : "—" })] }, school.id));
                    }) })] }) }));
}
function RecentActivityList({ loading }) {
    const { data: activities } = useRecentActivity();
    if (loading || !activities) {
        return (_jsx("div", { className: "space-y-3", children: [...Array(3)].map((_, i) => (_jsxs("div", { className: "flex items-start gap-3", children: [_jsx(Skeleton, { className: "w-2 h-2 rounded-full mt-2" }), _jsxs("div", { className: "flex-1", children: [_jsx(Skeleton, { className: "h-4 w-48 mb-1" }), _jsx(Skeleton, { className: "h-3 w-24" })] })] }, i))) }));
    }
    return (_jsxs("div", { className: "space-y-3", children: [activities.slice(0, 10).map((activity) => (_jsxs("div", { className: "flex items-start gap-3", children: [_jsx("span", { className: "w-2 h-2 rounded-full bg-brand-primary mt-2 flex-shrink-0" }), _jsxs("div", { children: [_jsx("p", { className: "text-sm text-role-admin-ink", children: activity.message }), _jsx("p", { className: "text-xs text-role-admin-muted", children: new Date(activity.timestamp).toLocaleString() })] })] }, activity.id))), activities.length === 0 && (_jsx("p", { className: "text-sm text-role-admin-muted", children: "No recent activity" }))] }));
}
export function AdminOverview() {
    const { data: stats, isLoading: statsLoading } = usePlatformStats();
    const { data: schoolsData, isLoading: schoolsLoading } = useAdminSchools({ page_size: 50 });
    const schools = schoolsData?.schools ?? [];
    const formatCurrency = (amount) => new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(amount);
    return (_jsx(AdminLayout, { pageTitle: "Platform overview", topNavAction: _jsx(Link, { to: "/kaihle-admin/schools?action=create", children: _jsx(Button, { children: "+ Add school" }) }), children: _jsxs("div", { className: "space-y-6", children: [_jsxs("section", { children: [_jsx("h2", { className: "text-xs font-bold uppercase tracking-widest text-role-admin-muted mb-4", children: "Platform KPIs" }), _jsxs("div", { className: "grid grid-cols-1 md:grid-cols-3 gap-4", children: [_jsx(KPICard, { icon: _jsx(TrendingUp, { className: "w-6 h-6" }), label: "Schools", value: stats?.total_schools ?? 0, loading: statsLoading }), _jsx(KPICard, { icon: _jsx(Users, { className: "w-6 h-6" }), label: "Students", value: stats?.total_students ?? 0, loading: statsLoading }), _jsx(KPICard, { icon: _jsx(DollarSign, { className: "w-6 h-6" }), label: "MRR", value: formatCurrency(stats?.mrr ?? 0), valueColor: "text-brand-primary", loading: statsLoading })] })] }), _jsx("section", { children: _jsx(Card, { className: "bg-white border border-role-admin-border", children: _jsxs("div", { className: "flex items-center gap-2 mb-4", children: [_jsx(Activity, { className: "w-5 h-5 text-role-admin-muted" }), _jsxs("span", { className: "text-sm font-semibold text-role-admin-ink", children: ["Uptime: ", stats?.uptime ?? "—", "% | Latency: ", stats?.latency_ms ?? "—", "ms"] })] }) }) }), _jsxs("section", { children: [_jsx("h2", { className: "text-xs font-bold uppercase tracking-widest text-role-admin-muted mb-4", children: "School status" }), _jsx(Card, { className: "bg-white border border-role-admin-border p-0 overflow-hidden", children: _jsx(SchoolStatusTable, { schools: schools, loading: schoolsLoading }) })] }), _jsxs("section", { children: [_jsx("h2", { className: "text-xs font-bold uppercase tracking-widest text-role-admin-muted mb-4", children: "Recent activity" }), _jsx(Card, { className: "bg-white border border-role-admin-border", children: _jsx(RecentActivityList, { loading: schoolsLoading }) })] })] }) }));
}
