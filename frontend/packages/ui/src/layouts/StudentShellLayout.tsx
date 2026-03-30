import React from "react";
import { LogOut } from "lucide-react";

export type StudentNavItem = "home" | "progress" | "study" | "assessments";

export interface StudentClassItem {
  id: string;
  name: string;
  isLocked: boolean;
}

export interface StudentShellLayoutProps {
  children: React.ReactNode;
  /** Content for the header greeting area */
  headerContent?: React.ReactNode;
  activeNav?: StudentNavItem;
  studentName?: string;
  studentInitials?: string;
  gradeInfo?: string;
  classes?: StudentClassItem[];
  onLogout?: () => void;
  onNavClick?: (nav: StudentNavItem) => void;
  onClassClick?: (classId: string) => void;
}

/**
 * Student shell layout with 200px left sidebar + main content area.
 * Based on student_dashboard.html mockup.
 *
 * Layout structure:
 * - Container: flex, white bg, border-radius:12px, shadow
 * - Left sidebar: width:200px, white bg, border-r border-role-student-border
 * - Main content: flex:1, vertical flex with header + scrollable content
 */
export function StudentShellLayout({
  children,
  headerContent,
  activeNav = "home",
  studentName = "",
  studentInitials = "",
  gradeInfo = "",
  classes = [],
  onLogout,
  onNavClick,
  onClassClick,
}: StudentShellLayoutProps) {
  const navItems: { key: StudentNavItem; label: string; icon: string }[] = [
    { key: "home", label: "Home", icon: "" },
    { key: "progress", label: "My progress", icon: "📈" },
    { key: "study", label: "Study plans", icon: "📚" },
    { key: "assessments", label: "Assessments", icon: "✓" },
  ];

  return (
    <div className="flex min-h-screen bg-role-student-bg">
      {/* Sidebar - 200px width */}
      <aside className="w-[200px] bg-white border-r border-role-student-border flex flex-col flex-shrink-0">
        {/* Logo */}
        <div className="px-4 py-3.5 border-b border-role-student-border">
          <span className="font-bold text-brand-ink italic text-base tracking-tight">
            Kaihle
          </span>
        </div>

        {/* Learn section */}
        <div className="px-3 pt-3 pb-1">
          <span className="text-[9px] font-bold uppercase tracking-widest text-brand-muted">
            Learn
          </span>
        </div>

        {/* Nav items */}
        <nav className="px-2 space-y-0.5">
          {navItems.map((item) => {
            const isActive = activeNav === item.key;
            return (
              <button
                key={item.key}
                onClick={() => onNavClick?.(item.key)}
                className={`w-full flex items-center gap-2 px-3 py-1.5 rounded-md text-xs transition-colors min-h-[44px] focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2 ${
                  isActive
                    ? "bg-brand-light text-brand-primary font-semibold"
                    : "text-brand-muted hover:text-brand-ink hover:bg-brand-border-soft"
                }`}
                aria-current={isActive ? "page" : undefined}
              >
                {isActive && (
                  <span
                    className="w-1.5 h-1.5 rounded-full bg-brand-primary flex-shrink-0"
                    aria-label="active"
                  />
                )}
                {item.icon && (
                  <span
                    className="w-4 text-center text-[13px]"
                    aria-hidden="true"
                  >
                    {item.icon}
                  </span>
                )}
                <span className={!isActive && !item.icon ? "ml-5" : ""}>
                  {item.label}
                </span>
              </button>
            );
          })}
        </nav>

        {/* Classes section */}
        {classes.length > 0 && (
          <>
            <div className="px-3 pt-4 pb-1">
              <span className="text-[9px] font-bold uppercase tracking-widest text-brand-muted">
                Classes
              </span>
            </div>
            <nav className="px-2 space-y-0.5">
              {classes.map((cls) => (
                <button
                  key={cls.id}
                  onClick={() => onClassClick?.(cls.id)}
                  className="w-full flex items-center gap-2 px-3 py-1.5 rounded-md text-xs text-brand-muted hover:text-brand-ink hover:bg-brand-border-soft transition-colors min-h-[44px] focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2"
                >
                  <span
                    className="w-4 text-center text-[13px]"
                    aria-hidden="true"
                  >
                    ◫
                  </span>
                  {cls.isLocked ? (
                    <span className="text-brand-gold">🔒 {cls.name}</span>
                  ) : (
                    <span className="truncate">{cls.name}</span>
                  )}
                </button>
              ))}
            </nav>
          </>
        )}

        {/* Profile section at bottom */}
        <div className="mt-auto px-3 py-3 border-t border-role-student-border">
          <div className="flex items-center gap-2">
            <div
              className="w-7 h-7 rounded-full bg-brand-light flex items-center justify-center text-[10px] font-bold text-brand-primary flex-shrink-0"
              aria-label={`Profile avatar for ${studentName}`}
            >
              {studentInitials || studentName?.charAt(0) || "?"}
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-[11px] font-semibold text-brand-ink truncate">
                {studentName}
              </div>
              {gradeInfo && (
                <div className="text-[9px] text-brand-muted truncate">
                  {gradeInfo}
                </div>
              )}
            </div>
          </div>
          {onLogout && (
            <button
              onClick={onLogout}
              className="mt-2 w-full flex items-center gap-1.5 px-2 py-1.5 text-xs text-brand-muted hover:text-brand-red transition-colors min-h-[36px] rounded-md hover:bg-brand-red/5 focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2"
            >
              <LogOut className="w-3.5 h-3.5" aria-hidden="true" />
              <span>Logout</span>
            </button>
          )}
        </div>
      </aside>

      {/* Main content area */}
      <main className="flex-1 flex flex-col overflow-hidden">
        {/* Header - 50px height */}
        <header className="h-[50px] bg-white border-b border-role-student-border flex items-center px-4 flex-shrink-0">
          {headerContent}
        </header>

        {/* Scrollable content */}
        <div className="flex-1 overflow-y-auto p-4">{children}</div>
      </main>
    </div>
  );
}
