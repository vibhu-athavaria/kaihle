import { LucideIcon } from "lucide-react";
import {
  LayoutDashboard,
  Building2,
  Users,
  ClipboardList,
  Settings,
  Archive,
  Cog,
  LogOut,
  FileText,
  Video,
  BarChart3,
  BookOpen,
  Library,
  GraduationCap,
  Terminal,
} from "lucide-react";
import { NavItem } from "./NavItem";

interface SidebarProps {
  variant: "teacher" | "school-admin" | "admin";
  onLogout?: () => void;
}

interface NavSection {
  section: string;
  items: { label: string; href: string; icon: LucideIcon }[];
}

const teacherSections: NavSection[] = [
  {
    section: "MY WORKSPACE",
    items: [
      { label: "Home", href: "/teacher/dashboard", icon: LayoutDashboard },
      { label: "Classes", href: "/teacher/classes", icon: Building2 },
      { label: "Students", href: "/teacher/students", icon: Users },
      {
        label: "Assessments",
        href: "/teacher/assessments",
        icon: ClipboardList,
      },
    ],
  },
  {
    section: "TOOLS",
    items: [
      { label: "Lesson Plans", href: "/teacher/lesson-plans", icon: BookOpen },
      {
        label: "Content Review",
        href: "/teacher/content-review",
        icon: FileText,
      },
    ],
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
        label: "Curriculum",
        href: "/kaihle-admin/curriculum",
        icon: Library,
      },
      {
        label: "Grades",
        href: "/kaihle-admin/grades",
        icon: GraduationCap,
      },
      {
        label: "Assessment Questions",
        href: "/kaihle-admin/question-bank",
        icon: FileText,
      },
      {
        label: "Video Library",
        href: "/kaihle-admin/content/videos",
        icon: Video,
      },
    ],
  },
  {
    section: "SYSTEM",
    items: [
      { label: "Logs", href: "/kaihle-admin/logs", icon: Archive },
      { label: "Config", href: "/kaihle-admin/config", icon: Cog },
      { label: "Scripts", href: "/kaihle-admin/scripts", icon: Terminal },
    ],
  },
];

function getCurrentPath(): string {
  if (typeof window !== "undefined") {
    return window.location.pathname;
  }
  return "";
}

export function Sidebar({ variant, onLogout }: SidebarProps) {
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
              const isActive =
                item.href === currentPath ||
                (item.href !== "#" &&
                  currentPath.startsWith(item.href.split("?")[0]));

              return (
                <NavItem
                  key={item.href}
                  label={item.label}
                  href={item.href}
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
