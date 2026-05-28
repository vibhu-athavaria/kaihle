import React from "react";
import { Sidebar, TopNav } from "../components/nav";
import { Toaster } from "../toast";

interface DashboardLayoutProps {
  variant: "teacher" | "school-admin";
  children: React.ReactNode;
  pageTitle: string;
  pageSubtitle?: string;
  topNavAction?: React.ReactNode;
  onLogout?: () => void;
  permissions?: Record<string, boolean> | null;
  settingsHref?: string;
}

export function DashboardLayout({
  variant,
  children,
  pageTitle,
  pageSubtitle,
  topNavAction,
  onLogout,
  permissions,
  settingsHref,
}: DashboardLayoutProps) {
  const bgClass =
    variant === "teacher" ? "bg-role-teacher-bg" : "bg-role-school-bg";

  const defaultSettingsHref =
    variant === "teacher" ? "/teacher/settings" : "/school-admin/settings";

  return (
    <div className={`flex h-screen overflow-hidden ${bgClass}`}>
      <Sidebar
        variant={variant}
        onLogout={onLogout}
        permissions={permissions}
        settingsHref={settingsHref ?? defaultSettingsHref}
      />
      <div className="flex flex-col flex-1 min-w-0 overflow-hidden">
        <TopNav
          pageTitle={pageTitle}
          pageSubtitle={pageSubtitle}
          topNavAction={topNavAction}
        />
        <main className="flex-1 overflow-y-auto p-6">{children}</main>
      </div>
      <Toaster />
    </div>
  );
}
