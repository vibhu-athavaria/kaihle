import { jsx as _jsx, jsxs as _jsxs, Fragment as _Fragment } from "react/jsx-runtime";
import { useState } from "react";
import { Link } from "react-router-dom";
import { DashboardLayout } from "@kaihle/ui";
import { Card } from "@kaihle/ui";
import { Badge } from "@kaihle/ui";
import { Button } from "@kaihle/ui";
import { MoreVertical, Mail, UserX, UserCheck, RefreshCw } from "lucide-react";
import { useSchoolUsers, useInviteUser, useUpdateUser, } from "../../hooks/useSchoolAdmin";
import { InviteUserModal } from "./InviteUserModal";
const roleTabs = [
    { value: "TEACHER", label: "Teachers" },
    { value: "STUDENT", label: "Students" },
    { value: "PARENT", label: "Parents" },
];
function getStatusBadge(status) {
    switch (status) {
        case "ACTIVE":
            return _jsx(Badge, { variant: "success", children: "\u25CF Active" });
        case "INVITED":
            return (_jsx(Badge, { variant: "gold", pulse: true, children: "\u25CB Invited" }));
        case "INACTIVE":
            return _jsx(Badge, { variant: "danger", children: "\u2715 Inactive" });
        default:
            return _jsx(Badge, { variant: "neutral", children: status });
    }
}
function UserRow({ user, onResendInvite, onToggleStatus, }) {
    const [showMenu, setShowMenu] = useState(false);
    const initials = `${user.first_name[0]}${user.last_name[0]}`.toUpperCase();
    return (_jsxs("tr", { className: "border-b border-brand-border-soft hover:bg-brand-light/30", children: [_jsx("td", { className: "py-3 px-4", children: _jsxs("div", { className: "flex items-center gap-3", children: [_jsx("div", { className: "w-8 h-8 rounded-full bg-brand-light text-brand-primary font-bold text-xs flex items-center justify-center", children: initials }), _jsxs("div", { children: [_jsxs("p", { className: "text-sm font-medium text-brand-ink", children: [user.first_name, " ", user.last_name] }), _jsx("p", { className: "text-xs text-brand-muted", children: user.email })] })] }) }), _jsx("td", { className: "py-3 px-4", children: getStatusBadge(user.status) }), _jsxs("td", { className: "py-3 px-4 relative", children: [_jsx("button", { onClick: () => setShowMenu(!showMenu), className: "p-1 hover:bg-gray-100 rounded", "aria-label": "Actions", children: _jsx(MoreVertical, { className: "w-4 h-4 text-brand-muted" }) }), showMenu && (_jsxs(_Fragment, { children: [_jsx("div", { className: "fixed inset-0", onClick: () => setShowMenu(false) }), _jsxs("div", { className: "absolute right-4 top-8 bg-white border border-brand-border rounded-lg shadow-lg py-1 z-10 min-w-[160px]", children: [user.status === "INVITED" && (_jsxs("button", { onClick: () => {
                                            onResendInvite(user);
                                            setShowMenu(false);
                                        }, className: "w-full px-4 py-2 text-left text-sm text-brand-ink hover:bg-gray-50 flex items-center gap-2", children: [_jsx(RefreshCw, { className: "w-4 h-4" }), "Resend invite"] })), user.status === "ACTIVE" && (_jsxs("button", { onClick: () => {
                                            onToggleStatus(user);
                                            setShowMenu(false);
                                        }, className: "w-full px-4 py-2 text-left text-sm text-brand-red hover:bg-gray-50 flex items-center gap-2", children: [_jsx(UserX, { className: "w-4 h-4" }), "Deactivate"] })), user.status === "INACTIVE" && (_jsxs("button", { onClick: () => {
                                            onToggleStatus(user);
                                            setShowMenu(false);
                                        }, className: "w-full px-4 py-2 text-left text-sm text-brand-green hover:bg-gray-50 flex items-center gap-2", children: [_jsx(UserCheck, { className: "w-4 h-4" }), "Reactivate"] }))] })] }))] })] }));
}
export function UserManagement() {
    const [activeTab, setActiveTab] = useState("TEACHER");
    const [isModalOpen, setIsModalOpen] = useState(false);
    const { data: users, isLoading } = useSchoolUsers(activeTab);
    const inviteUser = useInviteUser();
    const updateUser = useUpdateUser();
    const handleInvite = async (data) => {
        await inviteUser.mutateAsync(data);
    };
    const handleResendInvite = (user) => {
        console.log("Resend invite to", user.email);
    };
    const handleToggleStatus = (user) => {
        const newStatus = user.status === "ACTIVE" ? "INACTIVE" : "ACTIVE";
        updateUser.mutate({ userId: user.id, status: newStatus });
    };
    const getTabHref = (tab) => {
        return `/school/users?role=${tab.toLowerCase()}`;
    };
    return (_jsx(DashboardLayout, { variant: "school-admin", pageTitle: "Users", pageSubtitle: "Manage teachers, students, and parents at your school", topNavAction: _jsxs(Button, { variant: "primary", size: "sm", onClick: () => setIsModalOpen(true), children: [_jsx(Mail, { className: "w-4 h-4 mr-1" }), "Invite user"] }), children: _jsxs("div", { className: "space-y-6", children: [_jsx("div", { className: "border-b border-brand-border", children: _jsx("nav", { className: "flex gap-6", "aria-label": "User roles", children: roleTabs.map((tab) => {
                            const isActive = activeTab === tab.value;
                            return (_jsx(Link, { to: getTabHref(tab.value), onClick: (e) => {
                                    e.preventDefault();
                                    setActiveTab(tab.value);
                                }, className: `py-3 px-1 text-sm font-medium border-b-2 transition-colors ${isActive
                                    ? "text-brand-primary border-brand-primary"
                                    : "text-brand-muted border-transparent hover:text-brand-ink"}`, "aria-current": isActive ? "page" : undefined, children: tab.label }, tab.value));
                        }) }) }), _jsx(Card, { variant: "default", className: "bg-white border-role-school-border overflow-hidden", children: isLoading ? (_jsx("div", { className: "p-8 text-center text-brand-muted", children: "Loading..." })) : users && users.length > 0 ? (_jsxs(_Fragment, { children: [_jsx("div", { className: "overflow-x-auto", children: _jsxs("table", { className: "w-full", children: [_jsx("thead", { children: _jsxs("tr", { className: "border-b border-brand-border text-left", children: [_jsx("th", { className: "py-3 px-4 text-xs font-bold uppercase text-brand-muted", children: "Name" }), _jsx("th", { className: "py-3 px-4 text-xs font-bold uppercase text-brand-muted", children: "Status" }), _jsx("th", { className: "py-3 px-4 text-xs font-bold uppercase text-brand-muted w-12", children: "Actions" })] }) }), _jsx("tbody", { children: users.map((user) => (_jsx(UserRow, { user: user, onResendInvite: handleResendInvite, onToggleStatus: handleToggleStatus }, user.id))) })] }) }), _jsxs("div", { className: "p-4 border-t border-brand-border text-sm text-brand-muted", children: ["Showing ", users.length, " ", activeTab.toLowerCase(), "s"] })] })) : (_jsxs("div", { className: "p-8 text-center text-brand-muted", children: ["No ", activeTab.toLowerCase(), "s found. Invite your first", " ", activeTab.toLowerCase(), " to get started."] })) }), _jsx(InviteUserModal, { isOpen: isModalOpen, onClose: () => setIsModalOpen(false), onInvite: handleInvite, defaultRole: activeTab })] }) }));
}
