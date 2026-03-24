import React from "react";
import { Sidebar, TopNav } from "../components/nav";
import { Toaster } from "../toast";

interface AdminLayoutProps {
  children: React.ReactNode;
  pageTitle: string;
  pageSubtitle?: string;
  topNavAction?: React.ReactNode;
  onLogout?: () => void;
}

export function AdminLayout({
  children,
  pageTitle,
  pageSubtitle,
  topNavAction,
  onLogout,
}: AdminLayoutProps) {
  return (
    <div className="flex h-screen overflow-hidden bg-role-admin-bg">
      <Sidebar variant="admin" onLogout={onLogout} />
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
