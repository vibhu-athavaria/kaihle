import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useState, useEffect } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { AdminLayout } from "@kaihle/ui";
import { Card, Badge, Button, Skeleton } from "@kaihle/ui";
import { useAdminSchools } from "../../hooks/useKaihleAdmin";
import { Plus, Filter } from "lucide-react";
import { AdminCreateSchoolModal } from "./AdminCreateSchoolModal";
const filterTabs = [
    { key: "ALL", label: "All" },
    { key: "ACTIVE", label: "Active" },
    { key: "TRIAL", label: "Trial" },
    { key: "SUSPENDED", label: "Suspended" },
];
function getStatusBadgeVariant(status) {
    switch (status) {
        case "ACTIVE":
            return "success";
        case "TRIAL":
            return "warning";
        case "SUSPENDED":
            return "danger";
        default:
            return "neutral";
    }
}
function SchoolsTable({ schools, loading, }) {
    if (loading) {
        return (_jsx("div", { className: "space-y-3", children: [...Array(5)].map((_, i) => (_jsxs("div", { className: "flex items-center gap-4 p-4 border border-role-admin-border rounded-xl", children: [_jsx(Skeleton, { className: "h-4 w-40" }), _jsx(Skeleton, { className: "h-4 w-20" }), _jsx(Skeleton, { className: "h-4 w-20" }), _jsx(Skeleton, { className: "h-4 w-20" })] }, i))) }));
    }
    if (schools.length === 0) {
        return (_jsx("div", { className: "text-center py-12", children: _jsx("p", { className: "text-role-admin-muted", children: "No schools found" }) }));
    }
    return (_jsx("div", { className: "overflow-x-auto", children: _jsxs("table", { className: "w-full", children: [_jsx("thead", { children: _jsxs("tr", { className: "border-b border-role-admin-border", children: [_jsx("th", { className: "text-left py-3 px-4 text-xs font-bold uppercase tracking-widest text-role-admin-muted", children: "Name" }), _jsx("th", { className: "text-left py-3 px-4 text-xs font-bold uppercase tracking-widest text-role-admin-muted", children: "Plan" }), _jsx("th", { className: "text-left py-3 px-4 text-xs font-bold uppercase tracking-widest text-role-admin-muted", children: "Status" }), _jsx("th", { className: "text-left py-3 px-4 text-xs font-bold uppercase tracking-widest text-role-admin-muted", children: "Created" })] }) }), _jsx("tbody", { children: schools.map((school) => (_jsxs("tr", { className: "border-b border-role-admin-border hover:bg-gray-50 transition-colors cursor-pointer", children: [_jsxs("td", { className: "py-3 px-4", children: [_jsx(Link, { to: `/kaihle-admin/schools/${school.id}`, className: "text-sm font-semibold text-role-admin-ink hover:text-brand-primary", children: school.name }), school.country && (_jsxs("span", { className: "text-xs text-role-admin-muted ml-2", children: [school.country, school.city && `, ${school.city}`] }))] }), _jsx("td", { className: "py-3 px-4 text-sm text-role-admin-subtle", children: school.plan_tier }), _jsx("td", { className: "py-3 px-4", children: _jsx(Badge, { variant: getStatusBadgeVariant(school.subscription_status), children: school.subscription_status }) }), _jsx("td", { className: "py-3 px-4 text-sm text-role-admin-subtle", children: new Date(school.created_at).toLocaleDateString() })] }, school.id))) })] }) }));
}
export function AdminSchools() {
    const [searchParams, setSearchParams] = useSearchParams();
    const [activeFilter, setActiveFilter] = useState("ALL");
    const [showCreateModal, setShowCreateModal] = useState(false);
    useEffect(() => {
        if (searchParams.get("action") === "create") {
            setShowCreateModal(true);
            searchParams.delete("action");
            setSearchParams(searchParams);
        }
    }, [searchParams, setSearchParams]);
    const { data: schoolsData, isLoading } = useAdminSchools({
        page_size: 50,
        status: activeFilter === "ALL" ? undefined : activeFilter,
    });
    const schools = schoolsData?.schools ?? [];
    return (_jsxs(AdminLayout, { pageTitle: "Schools", topNavAction: _jsx(Button, { onClick: () => setShowCreateModal(true), icon: _jsx(Plus, { className: "w-4 h-4" }), children: "Add school" }), children: [_jsxs("div", { className: "space-y-6", children: [_jsxs("div", { className: "flex items-center gap-2 border-b border-role-admin-border pb-4", children: [_jsx(Filter, { className: "w-4 h-4 text-role-admin-muted" }), _jsx("div", { className: "flex gap-1", children: filterTabs.map((tab) => (_jsx("button", { onClick: () => setActiveFilter(tab.key), className: [
                                        "px-4 py-2 text-sm font-semibold rounded-lg transition-colors",
                                        activeFilter === tab.key
                                            ? "bg-brand-primary text-white"
                                            : "text-role-admin-subtle hover:bg-gray-100",
                                    ].join(" "), children: tab.label }, tab.key))) })] }), _jsx(Card, { className: "bg-white border border-role-admin-border p-0 overflow-hidden", children: _jsx(SchoolsTable, { schools: schools, loading: isLoading }) })] }), showCreateModal && (_jsx(AdminCreateSchoolModal, { onClose: () => setShowCreateModal(false) }))] }));
}
