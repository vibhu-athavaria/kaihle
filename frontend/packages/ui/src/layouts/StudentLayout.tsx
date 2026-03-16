import React from "react";
import { TopNav, BottomNav } from "../components/nav";

interface StudentLayoutProps {
  children: React.ReactNode;
  pageTitle?: string;
  activeNav?: "home" | "progress" | "study" | "assessments";
}

export function StudentLayout({
  children,
  pageTitle,
  activeNav = "home",
}: StudentLayoutProps) {
  return (
    <div className="min-h-screen bg-role-student-bg">
      <TopNav variant="student" pageTitle={pageTitle || "Kaihle"} />
      <main className="pb-20 md:pb-6 p-4 md:p-6">{children}</main>
      <BottomNav activeItem={activeNav} />
    </div>
  );
}
