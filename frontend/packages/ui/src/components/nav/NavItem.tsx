import { LucideIcon } from "lucide-react";

interface NavItemProps {
  label: string;
  href: string;
  icon?: LucideIcon;
  isActive: boolean;
  variant: "teacher" | "school-admin" | "admin";
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

export function NavItem({
  label,
  href,
  icon: Icon,
  isActive,
  variant,
}: NavItemProps) {
  const activeClass = activeClasses[variant];
  const inactiveClass = inactiveClasses[variant];

  return (
    <a
      href={href}
      className={[
        "flex items-center gap-2 px-3 py-2.5 mx-2 text-sm font-semibold transition-colors",
        isActive ? activeClass : inactiveClass,
      ].join(" ")}
      aria-current={isActive ? "page" : undefined}
    >
      {variant === "admin" && isActive && (
        <span className="w-1.5 h-1.5 rounded-full bg-brand-primary flex-shrink-0" />
      )}
      {Icon && <Icon className="w-5 h-5 flex-shrink-0" aria-hidden="true" />}
      <span>{label}</span>
    </a>
  );
}
