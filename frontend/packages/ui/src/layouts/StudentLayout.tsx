// packages/ui/src/layouts/StudentLayout.tsx
import React from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  Home,
  BarChart2,
  BookOpen,
  ClipboardList,
  Lock,
  LogOut,
} from "lucide-react";

export type StudentNavItem =
  | "home"
  | "progress"
  | "study-plans"
  | "assessments";

export interface StudentClass {
  id: string;
  name: string; // "Mathematics 9B"
  subjectName: string; // "Mathematics"
  subjectId: string; // UUID
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
}

// Subject dot color map — per DESIGN_SYSTEM.md §8 Subject Colors
const SUBJECT_DOT_COLORS: Record<string, string> = {
  Mathematics: "bg-brand-primary", // #1a5c38
  "Integrated Science": "bg-violet-600", // #7c3aed
  Biology: "bg-green-600", // #16a34a
  Chemistry: "bg-amber-600", // #d97706
  Physics: "bg-blue-600", // #2563eb
  "English Language": "bg-red-600", // #dc2626
  "English Literature": "bg-purple-600", // #9333ea
};
function getSubjectDotColor(subjectName: string): string {
  return SUBJECT_DOT_COLORS[subjectName] ?? "bg-brand-muted";
}

// Nav item → route map
const NAV_ROUTES: Record<StudentNavItem, string> = {
  home: "/student/dashboard",
  progress: "/student/my-progress",
  "study-plans": "/student/study-plans",
  assessments: "/student/assessments",
};

// Greeting helper — shared by layout top nav
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
}: StudentLayoutProps) {
  const navigate = useNavigate();

  // Avatar initials — "Jane Doe" → "JD", "Jane" → "J"
  const initials = studentName
    .split(" ")
    .map((n) => n[0])
    .join("")
    .toUpperCase()
    .slice(0, 2);

  const firstName = studentName.split(" ")[0] ?? studentName;

  return (
    <div className="flex h-screen overflow-hidden bg-role-student-bg">
      {/* ── SIDEBAR ──────────────────────────────────────────── */}
      <aside
        className="w-[200px] flex-shrink-0 bg-white border-r border-role-student-border flex flex-col"
        aria-label="Sidebar"
      >
        {/* Logo row — h-[50px] must match topnav height */}
        <div className="h-[50px] flex items-center px-4 border-b border-role-student-border flex-shrink-0">
          <span className="font-display italic font-semibold text-sidebar-logo text-brand-ink">
            Kaihle
          </span>
        </div>

        {/* Nav */}
        <nav
          className="flex-1 overflow-y-auto py-2"
          aria-label="Main navigation"
        >
          {/* LEARN section */}
          <div className="px-3.5 pt-4 pb-1 font-sans font-bold text-sidebar-label uppercase tracking-[0.8px] text-brand-muted">
            Learn
          </div>

          {[
            { key: "home" as StudentNavItem, label: "Home", Icon: Home },
            {
              key: "progress" as StudentNavItem,
              label: "My progress",
              Icon: BarChart2,
            },
            {
              key: "study-plans" as StudentNavItem,
              label: "Study plans",
              Icon: BookOpen,
            },
            {
              key: "assessments" as StudentNavItem,
              label: "Assessments",
              Icon: ClipboardList,
            },
          ].map(({ key, label, Icon }) => {
            const isActive = activeNav === key;
            return (
              <Link
                key={key}
                to={NAV_ROUTES[key]}
                aria-current={isActive ? "page" : undefined}
                className={[
                  "flex items-center gap-2 mx-1.5 px-3 py-7px rounded-nav",
                  "font-sans text-sidebar-nav transition-colors",
                  isActive
                    ? "bg-role-student-nav-active text-brand-primary font-semibold"
                    : "text-brand-muted hover:bg-gray-50 hover:text-brand-ink",
                ].join(" ")}
              >
                {isActive ? (
                  <span
                    className="w-[6px] h-[6px] rounded-full bg-brand-primary flex-shrink-0"
                    aria-hidden="true"
                  />
                ) : (
                  <Icon
                    className="w-[13px] h-[13px] flex-shrink-0"
                    aria-hidden="true"
                  />
                )}
                {label}
              </Link>
            );
          })}

          {/* CLASSES section — dynamic */}
          {classes.length > 0 && (
            <>
              <div className="px-3.5 pt-4 pb-1 font-sans font-bold text-sidebar-label uppercase tracking-[0.8px] text-brand-muted">
                Classes
              </div>
              {classes.map((cls) => {
                const isLocked = cls.diagnosticStatus !== "COMPLETED";
                const route = isLocked
                  ? cls.diagnosticAttemptId
                    ? `/student/assessments/${cls.diagnosticAttemptId}/take`
                    : `/student/classes/${cls.id}/diagnostic`
                  : `/student/classes/${cls.id}/topics`;
                return (
                  <Link
                    key={cls.id}
                    to={route}
                    className={[
                      "flex items-center gap-2 mx-1.5 px-3 py-7px rounded-nav",
                      "font-sans text-sidebar-nav transition-colors",
                      isLocked
                        ? "text-brand-gold hover:bg-role-student-nav-locked-hover"
                        : "text-brand-muted hover:bg-gray-50 hover:text-brand-ink",
                    ].join(" ")}
                  >
                    {isLocked ? (
                      <Lock
                        className="w-[11px] h-[11px] flex-shrink-0"
                        aria-hidden="true"
                      />
                    ) : (
                      <span
                        className={`w-[7px] h-[7px] rounded-full flex-shrink-0 ${getSubjectDotColor(
                          cls.subjectName,
                        )}`}
                        aria-hidden="true"
                      />
                    )}
                    {cls.name}
                  </Link>
                );
              })}
            </>
          )}
        </nav>

        {/* ── PROFILE CARD — pinned at sidebar bottom ──────────── */}
        <div className="border-t border-role-student-border flex-shrink-0">
          {/* Profile row → /student/settings on click */}
          <button
            type="button"
            onClick={() => navigate("/student/settings")}
            className="w-full flex items-center gap-2 px-3.5 py-3 hover:bg-gray-50 transition-colors text-left"
            aria-label={`${studentName} — open settings`}
          >
            <div
              className="w-[28px] h-[28px] rounded-full bg-brand-green-light flex items-center
                         justify-center font-sans font-bold text-topnav-sub text-brand-primary flex-shrink-0"
              aria-hidden="true"
            >
              {initials}
            </div>
            <div className="overflow-hidden min-w-0">
              <div className="font-sans font-semibold text-sidebar-profile text-brand-ink truncate leading-tight">
                {studentName}
              </div>
              <div className="font-sans text-sidebar-label text-brand-muted truncate leading-tight">
                {gradeName} · {curriculumName}
              </div>
            </div>
          </button>

          {/* Logout — separate button below profile row */}
          <button
            type="button"
            onClick={onLogout}
            className="w-full flex items-center gap-2 px-3.5 py-2.5
                       font-sans text-sidebar-profile text-brand-muted hover:text-brand-ink hover:bg-gray-50 transition-colors"
            aria-label="Log out"
          >
            <LogOut
              className="w-[13px] h-[13px] flex-shrink-0"
              aria-hidden="true"
            />
            Logout
          </button>
        </div>
      </aside>

      {/* ── MAIN AREA ─────────────────────────────────────────── */}
      <div className="flex flex-col flex-1 min-w-0 overflow-hidden">
        {/* Top nav — greeting lives HERE per DESIGN_SYSTEM.md §5.4 Top nav spec */}
        <header
          className="h-[50px] bg-white border-b border-role-student-border
                     flex items-center justify-between px-18px flex-shrink-0"
        >
          {/* Left: greeting + grade/curriculum */}
          <div>
            <div className="font-sans font-medium text-topnav-sub text-brand-ink leading-tight">
              {getGreeting()}, {firstName} 👋
            </div>
            {gradeName && curriculumName && (
              <div className="font-sans text-topnav-sub text-brand-muted leading-tight">
                {gradeName} · {curriculumName}
              </div>
            )}
          </div>

          {/* Right: avatar → settings */}
          <button
            type="button"
            onClick={() => navigate("/student/settings")}
            className="w-[28px] h-[28px] rounded-full bg-brand-green-light flex items-center
                       justify-center font-sans font-bold text-topnav-sub text-brand-primary
                       hover:opacity-80 transition-opacity flex-shrink-0"
            aria-label={`${studentName} — open settings`}
          >
            {initials}
          </button>
        </header>

        {/* Page content — children render here */}
        <main className="flex-1 overflow-y-auto p-[18px]">{children}</main>
      </div>
    </div>
  );
}
