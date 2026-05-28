// packages/ui/src/layouts/StudentLayout.tsx
import React from "react";
import { Link, useNavigate } from "react-router-dom";
// MVP: BarChart2 removed (was used by My Progress nav item — add back when re-enabling)
import {
  Home,
  ClipboardList,
  Settings,
  LogOut,
  PanelLeftClose,
  PanelLeftOpen,
} from "lucide-react";
import { useSidebarCollapsed } from "../hooks/useSidebarCollapsed";

export type StudentNavItem = "home" | "progress" | "assessments";

export interface StudentClass {
  id: string;
  name: string; // "Mathematics 9B"
  subjectName: string; // "Mathematics"
  subjectId: string; // UUID
  teacherName: string;
  diagnosticStatus: "PENDING" | "IN_PROGRESS" | "COMPLETED";
  diagnosticAttemptId: string | null;
}

export interface StudentLayoutProps {
  children: React.ReactNode;
  activeNav: StudentNavItem; // required — every page must pass this explicitly
  classes?: StudentClass[]; // enrolled classes — populates sidebar CLASSES section
  studentName: string; // "Jane Doe" — sidebar profile card + avatar + top nav greeting
  gradeName: string; // "Grade 9" — sidebar profile card + top nav subtitle
  curriculumName: string; // "Cambridge IGCSE" — sidebar profile card + top nav subtitle
  onLogout: () => void; // sidebar logout button
  assessmentBadge?: number; // count of new ACTIVE assessments not yet started
}

// Subject dot color map — per DESIGN_SYSTEM.md §8 Subject Colors
const SUBJECT_DOT_COLORS: Record<string, string> = {
  Mathematics: "bg-brand-primary",
  "Integrated Science": "bg-violet-600",
  Biology: "bg-green-600",
  Chemistry: "bg-amber-600",
  Physics: "bg-blue-600",
  "English Language": "bg-red-600",
  "English Literature": "bg-purple-600",
};
function getSubjectDotColor(subjectName: string): string {
  return SUBJECT_DOT_COLORS[subjectName] ?? "bg-brand-muted";
}

const NAV_ROUTES: Record<StudentNavItem, string> = {
  home: "/student/dashboard",
  progress: "/student/my-progress",
  assessments: "/student/assessments",
};

function getGreeting(): string {
  const h = new Date().getHours();
  if (h < 12) return "Good morning";
  if (h < 18) return "Good afternoon";
  return "Good evening";
}

export function StudentLayout({
  children,
  activeNav,
  classes = [],
  studentName,
  gradeName,
  curriculumName,
  onLogout,
  assessmentBadge,
}: StudentLayoutProps) {
  const navigate = useNavigate();
  const { collapsed, toggle } = useSidebarCollapsed();

  const initials = studentName
    .split(" ")
    .map((n) => n[0])
    .join("")
    .toUpperCase()
    .slice(0, 2);

  const firstName = studentName.split(" ")[0] ?? studentName;

  const navItemClass = (isActive: boolean) =>
    [
      "relative flex items-center gap-2 rounded-lg",
      "text-sm font-medium transition-colors",
      collapsed ? "justify-center mx-1 px-2 py-2" : "mx-2 px-3 py-2",
      isActive
        ? "bg-role-student-nav-active text-brand-primary font-semibold"
        : "text-brand-body hover:bg-gray-50 hover:text-brand-ink",
    ].join(" ");

  return (
    <div className="flex h-screen overflow-hidden bg-role-student-bg">
      {/* ── SIDEBAR ──────────────────────────────────────────── */}
      <aside
        className={[
          "flex-shrink-0 bg-white border-r border-role-student-border flex flex-col transition-all duration-200",
          collapsed ? "w-14" : "w-56",
        ].join(" ")}
        aria-label="Sidebar"
      >
        {/* Logo row */}
        <div
          className={[
            "h-14 flex items-center border-b border-role-student-border flex-shrink-0",
            collapsed ? "justify-center px-0" : "px-4",
          ].join(" ")}
        >
          <span className="bg-brand-primary italic font-display font-bold text-lg text-white px-2 py-1 rounded-lg flex-shrink-0">
            K
          </span>
          {!collapsed && (
            <span className="ml-2 font-display font-bold text-sm text-brand-ink whitespace-nowrap">
              Kaihle
            </span>
          )}
        </div>

        {/* Nav */}
        <nav
          className="flex-1 overflow-y-auto py-2"
          aria-label="Main navigation"
        >
          {/* HOME section */}
          {!collapsed && (
            <p className="px-3 pt-3 pb-1 text-xs font-bold uppercase tracking-[0.8px] text-brand-muted">
              Home
            </p>
          )}
          {collapsed && <div className="pt-3" />}

          {[
            { key: "home" as StudentNavItem, label: "Dashboard", Icon: Home },
            // MVP: "My progress" nav item hidden — component and route retained
            // { key: "progress" as StudentNavItem, label: "My progress", Icon: BarChart2 },
          ].map(({ key, label, Icon }) => {
            const isActive = activeNav === key;
            return (
              <Link
                key={key}
                to={NAV_ROUTES[key]}
                aria-current={isActive ? "page" : undefined}
                title={collapsed ? label : undefined}
                className={navItemClass(isActive)}
              >
                {isActive && !collapsed ? (
                  <span
                    className="w-1.5 h-1.5 rounded-full bg-brand-primary flex-shrink-0"
                    aria-hidden="true"
                  />
                ) : (
                  <Icon className="w-4 h-4 flex-shrink-0" aria-hidden="true" />
                )}
                {!collapsed && label}
              </Link>
            );
          })}

          {/* MY CLASSES section */}
          {classes.length > 0 && (
            <>
              {!collapsed && (
                <p className="px-3 pt-4 pb-1 text-xs font-bold uppercase tracking-[0.8px] text-brand-muted">
                  My Classes
                </p>
              )}
              {collapsed && <div className="pt-3" />}
              {classes.map((cls) => (
                <Link
                  key={cls.id}
                  to={`/student/classes/${cls.id}`}
                  aria-label={cls.name}
                  title={collapsed ? cls.name : undefined}
                  className={[
                    "flex items-center rounded-lg text-sm font-medium text-brand-body hover:bg-gray-50 hover:text-brand-ink transition-colors",
                    collapsed
                      ? "justify-center mx-1 px-2 py-2"
                      : "gap-2 mx-2 px-3 py-2",
                  ].join(" ")}
                >
                  <span
                    className={`w-2 h-2 rounded-full flex-shrink-0 ${getSubjectDotColor(cls.subjectName)}`}
                    aria-hidden="true"
                  />
                  {!collapsed && cls.name}
                </Link>
              ))}
            </>
          )}

          {/* Divider */}
          <hr className="mx-3 my-2 border-brand-border" />

          {/* Assessments */}
          {(() => {
            const isActive = activeNav === "assessments";
            const showBadge = !!assessmentBadge && assessmentBadge > 0;
            return (
              <Link
                to={NAV_ROUTES["assessments"]}
                aria-current={isActive ? "page" : undefined}
                title={collapsed ? "Assessments" : undefined}
                className={navItemClass(isActive)}
              >
                {isActive && !collapsed ? (
                  <span
                    className="w-1.5 h-1.5 rounded-full bg-brand-primary flex-shrink-0"
                    aria-hidden="true"
                  />
                ) : (
                  <ClipboardList
                    className="w-4 h-4 flex-shrink-0"
                    aria-hidden="true"
                  />
                )}
                {!collapsed && "Assessments"}
                {showBadge && (
                  <span
                    className={[
                      "bg-brand-primary text-white text-xs font-bold w-5 h-5 flex items-center justify-center rounded-full leading-none flex-shrink-0",
                      collapsed ? "" : "ml-auto",
                    ].join(" ")}
                  >
                    {assessmentBadge > 9 ? "9+" : assessmentBadge}
                  </span>
                )}
              </Link>
            );
          })()}
        </nav>

        {/* ── SIDEBAR BOTTOM ───────────────────────────────────── */}
        <div className="border-t border-brand-border p-3 space-y-0.5">
          <button
            type="button"
            onClick={() => navigate("/student/settings")}
            title={collapsed ? "Settings" : undefined}
            className={[
              "w-full flex items-center gap-2 py-2 text-sm font-medium text-brand-body hover:text-brand-ink hover:bg-gray-50 rounded-lg transition-colors",
              collapsed ? "justify-center px-2" : "px-3",
            ].join(" ")}
            aria-label="Settings"
          >
            <Settings className="w-4 h-4 flex-shrink-0" aria-hidden="true" />
            {!collapsed && "Settings"}
          </button>
          <button
            type="button"
            onClick={onLogout}
            title={collapsed ? "Log out" : undefined}
            className={[
              "w-full flex items-center gap-2 py-2 text-sm font-medium text-brand-body hover:text-brand-ink hover:bg-gray-50 rounded-lg transition-colors",
              collapsed ? "justify-center px-2" : "px-3",
            ].join(" ")}
            aria-label="Log out"
          >
            <LogOut className="w-4 h-4 flex-shrink-0" aria-hidden="true" />
            {!collapsed && "Log out"}
          </button>

          {/* Collapse toggle */}
          <button
            type="button"
            onClick={toggle}
            title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            className={[
              "w-full flex items-center gap-2 py-2 text-sm font-medium text-brand-muted hover:text-brand-ink hover:bg-gray-50 rounded-lg transition-colors",
              collapsed ? "justify-center px-2" : "px-3",
            ].join(" ")}
          >
            {collapsed ? (
              <PanelLeftOpen
                className="w-4 h-4 flex-shrink-0"
                aria-hidden="true"
              />
            ) : (
              <>
                <PanelLeftClose
                  className="w-4 h-4 flex-shrink-0"
                  aria-hidden="true"
                />
                <span>Collapse</span>
              </>
            )}
          </button>
        </div>
      </aside>

      {/* ── MAIN AREA ─────────────────────────────────────────── */}
      <div className="flex flex-col flex-1 min-w-0 overflow-hidden">
        <header className="h-14 bg-white border-b border-role-student-border flex items-center justify-between px-6 flex-shrink-0">
          <div>
            <div className="font-display font-bold text-xl text-brand-ink leading-tight">
              {getGreeting()}, {firstName} 👋
            </div>
            {gradeName && curriculumName && (
              <div className="font-sans text-xs text-brand-body leading-tight">
                {gradeName} · {curriculumName}
              </div>
            )}
          </div>

          {/* Avatar → settings */}
          <button
            type="button"
            onClick={() => navigate("/student/settings")}
            className="w-8 h-8 rounded-full bg-role-student-nav-active flex items-center justify-center font-sans font-bold text-xs text-brand-primary hover:opacity-80 transition-opacity flex-shrink-0"
            aria-label={`${studentName} — open settings`}
          >
            {initials}
          </button>
        </header>

        <main className="flex-1 overflow-y-auto p-6">{children}</main>
      </div>
    </div>
  );
}
