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
  CreditCard,
  ArrowUpCircle,
  MessageSquare,
  PanelLeftClose,
  PanelLeftOpen,
} from "lucide-react";
import { hasPermission, Permission } from "@kaihle/types";
import { NavItem } from "./NavItem";
import { useSidebarCollapsed } from "../../hooks/useSidebarCollapsed";

interface SidebarProps {
  variant: "teacher" | "school-admin" | "admin";
  onLogout?: () => void;
  permissions?: Record<string, boolean> | null;
  settingsHref?: string;
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
      // Content Review temporarily hidden — re-enable when feature is ready
      // { label: "Content Review", href: "/teacher/content-review", icon: FileText },
    ],
  },
];

function buildSchoolAdminSections(
  permissions?: Record<string, boolean> | null,
): NavSection[] {
  const adminItems: { label: string; href: string; icon: LucideIcon }[] = [
    { label: "Analytics", href: "/school-admin/analytics", icon: BarChart3 },
  ];

  if (hasPermission(permissions, Permission.BILLING)) {
    adminItems.splice(1, 0, {
      label: "Billing",
      href: "/school-admin/billing",
      icon: CreditCard,
    });
  }

  return [
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
      items: adminItems,
    },
  ];
}

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
        label: "Content Review",
        href: "/kaihle-admin/content/review",
        icon: Video,
      },
      {
        label: "Promotion Queue",
        href: "/kaihle-admin/content/promotion",
        icon: ArrowUpCircle,
      },
      {
        label: "Suggestions",
        href: "/kaihle-admin/content/suggestions",
        icon: MessageSquare,
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

export function Sidebar({
  variant,
  onLogout,
  permissions,
  settingsHref,
}: SidebarProps) {
  const { collapsed, toggle } = useSidebarCollapsed();

  const sections =
    variant === "teacher"
      ? teacherSections
      : variant === "school-admin"
        ? buildSchoolAdminSections(permissions)
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
      className={[
        "flex-shrink-0 bg-white border-r flex flex-col transition-all duration-200",
        borderClass,
        collapsed ? "w-14" : "w-56",
      ].join(" ")}
      aria-label="Sidebar"
    >
      {/* Logo row */}
      <div
        className={`h-14 flex items-center border-b flex-shrink-0 ${borderClass} ${collapsed ? "justify-center px-0" : "px-4"}`}
      >
        <span
          className={`${logoMarkBg} italic font-display font-bold text-lg text-white px-2 py-1 rounded-lg flex-shrink-0`}
        >
          K
        </span>
        {!collapsed && (
          <span className="ml-2 font-display font-bold text-sm text-brand-ink whitespace-nowrap">
            Kaihle
          </span>
        )}
      </div>

      {/* Nav */}
      <nav className="flex-1 overflow-y-auto py-4" aria-label="Main navigation">
        {sections.map((section) => (
          <div key={section.section}>
            {!collapsed && (
              <div className="px-3 pt-4 pb-1 text-topnav-sub font-bold uppercase tracking-widest text-brand-muted">
                {section.section}
              </div>
            )}
            {collapsed && <div className="pt-3" />}
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
                  collapsed={collapsed}
                />
              );
            })}
          </div>
        ))}
      </nav>

      {/* Bottom: settings + logout + collapse */}
      <div className="border-t border-brand-border p-3 space-y-1">
        {settingsHref && (
          <a
            href={settingsHref}
            title={collapsed ? "Settings" : undefined}
            className={[
              "w-full flex items-center gap-2 py-2 text-sm font-medium text-brand-body hover:text-brand-ink hover:bg-brand-surface rounded-lg transition-colors",
              collapsed ? "justify-center px-2" : "px-3",
            ].join(" ")}
          >
            <Settings className="w-4 h-4 flex-shrink-0" aria-hidden="true" />
            {!collapsed && "Settings"}
          </a>
        )}
        {onLogout && (
          <button
            onClick={onLogout}
            title={collapsed ? "Log out" : undefined}
            className={[
              "w-full flex items-center gap-2 py-2 text-sm font-medium text-brand-body hover:text-brand-ink hover:bg-brand-surface rounded-lg transition-colors",
              collapsed ? "justify-center px-2" : "px-3",
            ].join(" ")}
          >
            <LogOut className="w-4 h-4 flex-shrink-0" aria-hidden="true" />
            {!collapsed && "Log out"}
          </button>
        )}
        <button
          onClick={toggle}
          title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          className={[
            "w-full flex items-center gap-2 py-2 text-sm font-medium text-brand-muted hover:text-brand-ink hover:bg-brand-surface rounded-lg transition-colors",
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
  );
}
