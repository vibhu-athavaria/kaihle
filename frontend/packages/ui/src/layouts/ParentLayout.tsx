import React from "react";
import { TopNav } from "../components/nav";
import { Toaster } from "../toast";

interface ParentLayoutProps {
  children: React.ReactNode;
}

export function ParentLayout({ children }: ParentLayoutProps) {
  return (
    <div className="min-h-screen bg-role-parent-bg">
      <TopNav variant="parent" pageTitle="" />
      <main className="p-4 max-w-lg mx-auto">{children}</main>
      <Toaster />
    </div>
  );
}
