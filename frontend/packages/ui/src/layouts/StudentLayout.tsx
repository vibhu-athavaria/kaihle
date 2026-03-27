import React from "react";
import { TopNav, BottomNav } from "../components/nav";
import { Toaster } from "../toast";

interface StudentLayoutProps {
  children: React.ReactNode;
  pageTitle?: string;
  activeNav?: "home" | "progress" | "study" | "assessments";
  onLogout?: () => void;
}

/**
 * Desktop top navigation tabs - hidden on mobile (md:hidden)
 * These match the BottomNav items but shown horizontally on desktop.
 * Per STUDENT_SCREENS.md §3: Top nav bar with 4 horizontal tabs + active green underline.
 */
const desktopNavItems = [
  { key: "home", label: "Home", href: "/student/dashboard" },
  { key: "progress", label: "Progress", href: "/student/my-progress" },
  { key: "study", label: "Study plans", href: "/student/study-plans" },
  { key: "assessments", label: "Assessments", href: "/student/assessments" },
];

function DesktopNavTabs() {
  // Get current path from window.location for tab highlighting
  const currentPath =
    typeof window !== "undefined" ? window.location.pathname : "";

  return (
    <div className="hidden md:flex border-b border-role-student-border bg-white">
      <div className="flex items-center gap-1 px-4">
        {desktopNavItems.map((item) => {
          const isActive =
            currentPath === item.href ||
            (item.key === "home" && currentPath === "/student/dashboard");

          return (
            <a
              key={item.key}
              href={item.href}
              className={`relative px-4 py-3 text-sm font-medium transition-colors min-h-[44px] flex items-center ${
                isActive
                  ? "text-brand-primary"
                  : "text-brand-muted hover:text-brand-ink"
              } focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2 rounded-md`}
              aria-current={isActive ? "page" : undefined}
            >
              {item.label}
              {isActive && (
                <span className="absolute bottom-0 left-0 right-0 h-0.5 bg-brand-primary" />
              )}
            </a>
          );
        })}
      </div>
    </div>
  );
}

export function StudentLayout({
  children,
  pageTitle,
  activeNav = "home",
  onLogout,
}: StudentLayoutProps) {
  return (
    <div className="min-h-screen bg-role-student-bg">
      <TopNav
        variant="student"
        pageTitle={pageTitle || "Kaihle"}
        onLogout={onLogout}
      />
      <DesktopNavTabs />
      <main className="pb-20 md:pb-6 p-4 md:p-6">{children}</main>
      <BottomNav activeItem={activeNav} />
      <Toaster />
    </div>
  );
}
