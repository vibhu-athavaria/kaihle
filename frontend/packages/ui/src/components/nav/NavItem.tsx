import { LucideIcon } from "lucide-react";

interface NavItemProps {
  label: string;
  href: string;
  icon?: LucideIcon;
  isActive: boolean;
  variant: "teacher" | "school-admin" | "admin";
  collapsed?: boolean;
  badge?: number;
}

const activeClasses: Record<NavItemProps["variant"], string> = {
  teacher:
    "bg-role-teacher-nav-active text-brand-gold-dark font-bold rounded-lg",
  "school-admin":
    "border-l-[3px] border-brand-primary bg-brand-light text-brand-primary rounded-r-lg rounded-l-none ml-0 mr-2",
  admin: "bg-gray-100 text-role-admin-ink rounded-lg",
};

const inactiveClasses: Record<NavItemProps["variant"], string> = {
  teacher: "text-brand-body hover:bg-gray-50 hover:text-brand-ink rounded-lg",
  "school-admin":
    "text-role-school-subtle hover:bg-brand-light/50 hover:text-brand-ink rounded-lg",
  admin:
    "text-role-admin-subtle hover:bg-gray-50 hover:text-role-admin-ink rounded-lg",
};

// Badge fill follows each role's action color (DESIGN_SYSTEM.md §5) — gold for Teacher,
// brand-primary green for School Admin and Kaihle Admin.
const badgeClasses: Record<NavItemProps["variant"], string> = {
  teacher: "bg-brand-gold text-white",
  "school-admin": "bg-brand-primary text-white",
  admin: "bg-brand-primary text-white",
};

export function NavItem({
  label,
  href,
  icon: Icon,
  isActive,
  variant,
  collapsed = false,
  badge,
}: NavItemProps) {
  const activeClass = activeClasses[variant];
  const inactiveClass = inactiveClasses[variant];

  return (
    <a
      href={href}
      title={collapsed ? label : undefined}
      className={[
        "flex items-center gap-2 py-2.5 text-sm font-semibold transition-colors",
        collapsed ? "justify-center px-2 mx-1" : "px-3 mx-2",
        isActive ? activeClass : inactiveClass,
      ].join(" ")}
      aria-current={isActive ? "page" : undefined}
    >
      {variant === "admin" && isActive && !collapsed && (
        <span className="w-1.5 h-1.5 rounded-full bg-brand-primary flex-shrink-0" />
      )}
      {Icon && <Icon className="w-5 h-5 flex-shrink-0" aria-hidden="true" />}
      {!collapsed && <span className="flex-1">{label}</span>}
      {!collapsed && !!badge && badge > 0 && (
        <span
          className={`inline-flex items-center justify-center min-w-[18px] h-[18px] px-1 rounded-full text-[11px] font-bold flex-shrink-0 ${badgeClasses[variant]}`}
          aria-label={`${badge} pending`}
        >
          {badge}
        </span>
      )}
    </a>
  );
}
