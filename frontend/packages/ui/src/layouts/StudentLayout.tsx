// packages/ui/src/layouts/StudentLayout.tsx
import React from "react";
import { Link, useNavigate } from "react-router-dom";
import { Home, BarChart2, ClipboardList, Settings, LogOut } from "lucide-react";

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

  const initials = studentName
    .split(" ")
    .map((n) => n[0])
    .join("")
    .toUpperCase()
    .slice(0, 2);

  const firstName = studentName.split(" ")[0] ?? studentName;

  const navItemClass = (isActive: boolean) =>
    [
      "relative flex items-center gap-2 mx-2 px-3 py-2 rounded-lg",
      "text-sm font-medium transition-colors",
      isActive
        ? "bg-role-student-nav-active text-brand-primary font-semibold"
        : "text-brand-body hover:bg-gray-50 hover:text-brand-ink",
    ].join(" ");

  return (
    <div className="flex h-screen overflow-hidden bg-role-student-bg">
      {/* ── SIDEBAR ──────────────────────────────────────────── */}
      <aside
        className="w-56 flex-shrink-0 bg-white border-r border-role-student-border flex flex-col"
        aria-label="Sidebar"
      >
        {/* Logo row */}
        <div className="h-14 flex items-center px-4 border-b border-role-student-border flex-shrink-0">
          <span className="bg-brand-primary italic font-display font-bold text-lg text-white px-2 py-1 rounded-lg">
            K
          </span>
          <span className="ml-2 font-display font-bold text-sm text-brand-ink">
            Kaihle
          </span>
        </div>

        {/* Nav */}
        <nav
          className="flex-1 overflow-y-auto py-2"
          aria-label="Main navigation"
        >
          {/* HOME section */}
          <p className="px-3 pt-3 pb-1 text-xs font-bold uppercase tracking-[0.8px] text-brand-muted">
            Home
          </p>

          {[
            { key: "home" as StudentNavItem, label: "Dashboard", Icon: Home },
            {
              key: "progress" as StudentNavItem,
              label: "My progress",
              Icon: BarChart2,
            },
          ].map(({ key, label, Icon }) => {
            const isActive = activeNav === key;
            return (
              <Link
                key={key}
                to={NAV_ROUTES[key]}
                aria-current={isActive ? "page" : undefined}
                className={navItemClass(isActive)}
              >
                {isActive ? (
                  <span
                    className="w-1.5 h-1.5 rounded-full bg-brand-primary flex-shrink-0"
                    aria-hidden="true"
                  />
                ) : (
                  <Icon className="w-4 h-4 flex-shrink-0" aria-hidden="true" />
                )}
                {label}
              </Link>
            );
          })}

          {/* MY CLASSES section */}
          {classes.length > 0 && (
            <>
              <p className="px-3 pt-4 pb-1 text-xs font-bold uppercase tracking-[0.8px] text-brand-muted">
                My Classes
              </p>
              {classes.map((cls) => (
                <Link
                  key={cls.id}
                  to={`/student/classes/${cls.id}`}
                  aria-label={cls.name}
                  className="flex items-center gap-2 mx-2 px-3 py-2 rounded-lg text-sm font-medium text-brand-body hover:bg-gray-50 hover:text-brand-ink transition-colors"
                >
                  <span
                    className={`w-2 h-2 rounded-full flex-shrink-0 ${getSubjectDotColor(cls.subjectName)}`}
                    aria-hidden="true"
                  />
                  {cls.name}
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
                className={navItemClass(isActive)}
              >
                {isActive ? (
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
                Assessments
                {showBadge && (
                  <span className="ml-auto bg-brand-primary text-white text-xs font-bold w-5 h-5 flex items-center justify-center rounded-full leading-none flex-shrink-0">
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
            className="w-full flex items-center gap-2 px-3 py-2 text-sm font-medium text-brand-body hover:text-brand-ink hover:bg-gray-50 rounded-lg transition-colors"
            aria-label="Settings"
          >
            <Settings className="w-4 h-4 flex-shrink-0" aria-hidden="true" />
            Settings
          </button>
          <button
            type="button"
            onClick={onLogout}
            className="w-full flex items-center gap-2 px-3 py-2 text-sm font-medium text-brand-body hover:text-brand-ink hover:bg-gray-50 rounded-lg transition-colors"
            aria-label="Log out"
          >
            <LogOut className="w-4 h-4 flex-shrink-0" aria-hidden="true" />
            Log out
          </button>
          {/* Profile card — name and grade */}
          <div className="flex items-center gap-2 px-3 py-2 mt-1 border-t border-brand-border-soft pt-3">
            <div className="w-7 h-7 rounded-full bg-role-student-nav-active flex items-center justify-center font-sans font-bold text-xs text-brand-primary flex-shrink-0">
              {initials}
            </div>
            <div className="min-w-0">
              <div className="text-xs font-semibold text-brand-ink truncate">
                {studentName}
              </div>
              <div className="text-xs text-brand-muted truncate">
                {gradeName}
              </div>
            </div>
          </div>
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
