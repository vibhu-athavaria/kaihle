import { Home, BarChart2, BookOpen, ClipboardList } from "lucide-react";

type BottomNavItem = "home" | "progress" | "study" | "assessments";

interface BottomNavProps {
  activeItem?: BottomNavItem;
  className?: string;
}

const navItems: {
  key: BottomNavItem;
  label: string;
  href: string;
  icon: typeof Home;
}[] = [
  { key: "home", label: "Home", href: "/student/dashboard", icon: Home },
  {
    key: "progress",
    label: "Progress",
    href: "/student/my-progress",
    icon: BarChart2,
  },
  {
    key: "study",
    label: "Study",
    href: "/student/study-plans",
    icon: BookOpen,
  },
  {
    key: "assessments",
    label: "Assessments",
    href: "/student/assessments",
    icon: ClipboardList,
  },
];

export function BottomNav({ activeItem, className = "" }: BottomNavProps) {
  return (
    <nav
      className={`md:hidden fixed bottom-0 inset-x-0 h-16 bg-white border-t border-role-student-border flex items-center ${className}`}
      aria-label="Student navigation"
    >
      {navItems.map((item) => {
        const isActive = activeItem === item.key;
        const Icon = item.icon;

        return (
          <a
            key={item.key}
            href={item.href}
            className="flex-1 flex flex-col items-center justify-center gap-1 min-h-[56px] transition-colors"
            aria-current={isActive ? "page" : undefined}
            aria-label={item.label}
          >
            <Icon
              className={`w-5 h-5 ${
                isActive ? "text-brand-primary" : "text-brand-muted"
              }`}
              aria-hidden="true"
            />
            <span
              className={`text-topnav-sub font-semibold ${
                isActive ? "text-brand-primary" : "text-brand-muted"
              }`}
            >
              {item.label}
            </span>
          </a>
        );
      })}
    </nav>
  );
}
