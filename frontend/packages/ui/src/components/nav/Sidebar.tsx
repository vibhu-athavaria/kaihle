import { LucideIcon } from "lucide-react";
import {
  LayoutDashboard,
  Map,
  ClipboardList,
  BookOpen,
  Users,
  BadgeDollarSign,
  BarChart3,
  Building2,
  Settings,
  Archive,
  Cog,
  LogOut,
  FileText,
} from "lucide-react";
import { NavItem } from "./NavItem";

interface SidebarProps {
  variant: "teacher" | "school-admin" | "admin";
  classId?: string;
  onLogout?: () => void;
}

interface NavSection {
  section: string;
  items: { label: string; href: string; icon: LucideIcon }[];
}

const teacherSections: NavSection[] = [
  {
    section: "MY CLASSES",
    items: [
      { label: "Dashboard", href: "/teacher/dashboard", icon: LayoutDashboard },
      {
        label: "Gap Map",
        href: "/teacher/classes/:classId/gap-map",
        icon: Map,
      },
      {
        label: "Assessments",
        href: "/teacher/classes/:classId/assessments",
        icon: ClipboardList,
      },
      {
        label: "Lesson Plans",
        href: "/teacher/classes/:classId/lesson-plans",
        icon: BookOpen,
      },
    ],
  },
  {
    section: "STUDENTS",
    items: [
      {
        label: "My Students",
        href: "/teacher/classes/:classId/students",
        icon: Users,
      },
    ],
  },
  {
    section: "TOOLS",
    items: [{ label: "Study Plans", href: "#", icon: BookOpen }],
  },
  {
    section: "ACCOUNT",
    items: [{ label: "Settings", href: "/teacher/settings", icon: Settings }],
  },
];

const schoolAdminSections: NavSection[] = [
  {
    section: "SCHOOL",
    items: [
      {
        label: "Dashboard",
        href: "/school-admin/dashboard",
        icon: LayoutDashboard,
      },
      { label: "Users", href: "/school-admin/users", icon: Users },
      { label: "Classes", href: "/school-admin/classes", icon: Building2 },
    ],
  },
  {
    section: "ADMIN",
    items: [
      { label: "Analytics", href: "/school-admin/analytics", icon: BarChart3 },
      {
        label: "Billing",
        href: "/school-admin/billing",
        icon: BadgeDollarSign,
      },
      { label: "Settings", href: "/school-admin/settings", icon: Settings },
    ],
  },
];

const adminSections: NavSection[] = [
  {
    section: "PLATFORM",
    items: [
      {
        label: "Overview",
        href: "/kaihle-admin/dashboard",
        icon: LayoutDashboard,
      },
      { label: "Schools", href: "/kaihle-admin/schools", icon: Building2 },
      { label: "Users", href: "/kaihle-admin/users", icon: Users },
      { label: "Billing", href: "/kaihle-admin/billing", icon: Settings },
    ],
  },
  {
    section: "CONTENT",
    items: [
      {
        label: "Assessment Questions",
        href: "/kaihle-admin/question-bank",
        icon: FileText,
      },
    ],
  },
  {
    section: "SYSTEM",
    items: [
      { label: "Logs", href: "/kaihle-admin/logs", icon: Archive },
      { label: "Config", href: "/kaihle-admin/config", icon: Cog },
    ],
  },
];

function getCurrentPath(): string {
  if (typeof window !== "undefined") {
    return window.location.pathname;
  }
  return "";
}

function resolveHref(href: string, classId?: string): string {
  if (href.includes(":classId") && classId) {
    return href.replace(":classId", classId);
  }
  return href;
}

export function Sidebar({ variant, classId, onLogout }: SidebarProps) {
  const sections =
    variant === "teacher"
      ? teacherSections
      : variant === "school-admin"
        ? schoolAdminSections
        : adminSections;

  const borderClass =
    variant === "school-admin"
      ? "border-role-school-border"
      : variant === "admin"
        ? "border-role-admin-border"
        : "border-role-teacher-border";

  const logoMarkBg =
    variant === "admin" ? "bg-role-admin-mark" : "bg-brand-primary";

  const currentPath = getCurrentPath();

  return (
    <aside
      className={`w-56 flex-shrink-0 bg-white border-r ${borderClass} flex flex-col`}
    >
      <div className={`h-14 flex items-center px-4 border-b ${borderClass}`}>
        <span
          className={`${logoMarkBg} italic font-display font-bold text-lg text-white px-2 py-1 rounded-lg`}
        >
          K
        </span>
        <span className="ml-2 font-display font-bold text-sm text-brand-ink">
          Kaihle
        </span>
      </div>

      <nav className="flex-1 overflow-y-auto py-4" aria-label="Main navigation">
        {sections.map((section) => (
          <div key={section.section}>
            <div className="px-3 pt-4 pb-1 text-topnav-sub font-bold uppercase tracking-widest text-brand-muted">
              {section.section}
            </div>
            {section.items.map((item) => {
              const resolvedHref = resolveHref(item.href, classId);
              const isActive =
                resolvedHref === currentPath ||
                (resolvedHref !== "#" &&
                  currentPath.startsWith(resolvedHref.split("?")[0]));

              return (
                <NavItem
                  key={item.href}
                  label={item.label}
                  href={resolvedHref}
                  icon={item.icon}
                  isActive={isActive}
                  variant={variant}
                />
              );
            })}
          </div>
        ))}
      </nav>

      {onLogout && (
        <div className="border-t border-brand-border p-3">
          <button
            onClick={onLogout}
            className="w-full flex items-center gap-2 px-3 py-2 text-sm font-medium text-brand-body hover:text-brand-ink hover:bg-brand-surface rounded-lg transition-colors"
          >
            <LogOut className="w-4 h-4" />
            Log out
          </button>
        </div>
      )}
    </aside>
  );
}
