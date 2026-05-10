// packages/ui/src/layouts/StudentLayout.tsx
import React from "react";
import { Link, useNavigate } from "react-router-dom";
import { Home, BarChart2, ClipboardList } from "lucide-react";

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
  onLogout: _onLogout,
  assessmentBadge,
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
    <div className="flex h-screen overflow-hidden bg-brand-bg">
      {/* ── SIDEBAR ──────────────────────────────────────────── */}
      <aside
        className="w-56 flex-shrink-0 bg-white border-r border-role-student-border flex flex-col"
        aria-label="Sidebar"
      >
        {/* Logo row — h-14 must match topnav height */}
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
          className="flex-1 overflow-y-auto py-4"
          aria-label="Main navigation"
        >
          {/* HOME section */}
          <div className="px-3 pt-4 pb-1 font-bold text-topnav-sub uppercase tracking-widest text-brand-muted">
            Home
          </div>

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
                className={[
                  "relative flex items-center gap-2 mx-2 px-3 py-2.5 rounded-lg",
                  "text-sm font-semibold transition-colors",
                  isActive
                    ? "bg-[#f0fdf4] text-brand-primary font-semibold"
                    : "text-brand-body hover:bg-gray-50 hover:text-brand-ink",
                ].join(" ")}
              >
                {isActive ? (
                  <span
                    className="w-[6px] h-[6px] rounded-full bg-brand-primary flex-shrink-0"
                    aria-hidden="true"
                  />
                ) : (
                  <Icon className="w-5 h-5 flex-shrink-0" aria-hidden="true" />
                )}
                {label}
              </Link>
            );
          })}

          {/* MY CLASSES section — dynamic, flat, no lock state distinction */}
          {classes.length > 0 && (
            <>
              <div className="px-3 pt-4 pb-1 font-bold text-topnav-sub uppercase tracking-widest text-brand-muted">
                My Classes
              </div>
              {classes.map((cls) => (
                <Link
                  key={cls.id}
                  to={`/student/classes/${cls.id}`}
                  aria-label={cls.name}
                  className={[
                    "flex items-center gap-2 mx-2 px-3 py-2.5 rounded-lg",
                    "text-sm font-semibold transition-colors",
                    "text-brand-body hover:bg-gray-50 hover:text-brand-ink",
                  ].join(" ")}
                >
                  <span
                    className={`w-[7px] h-[7px] rounded-full flex-shrink-0 ${getSubjectDotColor(cls.subjectName)}`}
                    aria-hidden="true"
                  />
                  {cls.name}
                </Link>
              ))}
            </>
          )}

          {/* Divider before Assessments */}
          <hr className="mx-3 my-3 border-brand-border" />

          {/* Assessments — no section label */}
          {(() => {
            const isActive = activeNav === "assessments";
            const showBadge = !!assessmentBadge && assessmentBadge > 0;
            return (
              <Link
                to={NAV_ROUTES["assessments"]}
                aria-current={isActive ? "page" : undefined}
                className={[
                  "relative flex items-center gap-2 mx-2 px-3 py-2.5 rounded-lg",
                  "text-sm font-semibold transition-colors",
                  isActive
                    ? "bg-[#f0fdf4] text-brand-primary font-semibold"
                    : "text-brand-body hover:bg-gray-50 hover:text-brand-ink",
                ].join(" ")}
              >
                {isActive ? (
                  <span
                    className="w-[6px] h-[6px] rounded-full bg-brand-primary flex-shrink-0"
                    aria-hidden="true"
                  />
                ) : (
                  <ClipboardList
                    className="w-5 h-5 flex-shrink-0"
                    aria-hidden="true"
                  />
                )}
                Assessments
                {showBadge && (
                  <span className="ml-auto bg-brand-primary text-white text-[8px] font-bold px-1.5 py-0.5 rounded-full leading-none">
                    {assessmentBadge}
                  </span>
                )}
              </Link>
            );
          })()}
        </nav>

        {/* ── SIDEBAR BOTTOM — profile card ───────────────────── */}
        <div className="border-t border-brand-border p-3 flex items-center gap-2">
          <button
            type="button"
            onClick={() => navigate("/student/settings")}
            className="w-7 h-7 rounded-full bg-[#f0fdf4] flex items-center justify-center
                       font-sans font-bold text-[11px] text-brand-primary
                       hover:opacity-80 transition-opacity flex-shrink-0"
            aria-label={`${studentName} — open settings`}
          >
            {initials}
          </button>
          <div className="min-w-0">
            <div className="text-[11px] font-semibold text-brand-ink truncate">
              {studentName}
            </div>
            <div className="text-[10px] text-brand-muted truncate">
              {gradeName}
            </div>
          </div>
        </div>
      </aside>

      {/* ── MAIN AREA ─────────────────────────────────────────── */}
      <div className="flex flex-col flex-1 min-w-0 overflow-hidden">
        {/* Top nav — greeting lives HERE per DESIGN_SYSTEM.md §5.4 Top nav spec */}
        <header
          className="h-14 bg-white border-b border-role-student-border
           flex items-center justify-between px-6 flex-shrink-0"
        >
          {/* Left: greeting + grade/curriculum */}
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

          {/* Right: avatar → settings */}
          <button
            type="button"
            onClick={() => navigate("/student/settings")}
            className="w-[28px] h-[28px] rounded-full bg-brand-green-light flex items-center
                       justify-center font-sans font-bold text-xs text-brand-primary
                       hover:opacity-80 transition-opacity flex-shrink-0"
            aria-label={`${studentName} — open settings`}
          >
            {initials}
          </button>
        </header>

        {/* Page content — children render here */}
        <main className="flex-1 overflow-y-auto p-6">{children}</main>
      </div>
    </div>
  );
}
