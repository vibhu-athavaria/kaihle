import { Link } from "react-router-dom";
import { ChevronRight } from "lucide-react";
import { roleDashboardMap } from "@/config/roleNavigation";
import { UserRole } from "@/types";
import clsx from "clsx";

export type BreadcrumbItem = {
  label: string;
  to?: string;
  icon?: React.ElementType;
};

type BreadcrumbProps = {
  role: UserRole;
  items: BreadcrumbItem[];
};

export const Breadcrumb = ({ role, items }: BreadcrumbProps) => {
  const root = roleDashboardMap[role];

  const fullItems: BreadcrumbItem[] = [
    {
      label: root.label,
      to: root.path,
      icon: root.icon,
    },
    ...items,
  ];

  return (
    <nav aria-label="Breadcrumb" className="mb-6">
      <ol className="flex items-center flex-wrap text-sm text-gray-500">
        {fullItems.map((item, index) => {
          const Icon = item.icon;
          const isLast = index === fullItems.length - 1;

          return (
            <li key={index} className="flex items-center">
              {index > 0 && (
                <ChevronRight className="w-4 h-4 mx-2 text-gray-400" />
              )}

              {item.to && !isLast ? (
                <Link
                  to={item.to}
                  className="flex items-center gap-1 hover:text-blue-600 transition-colors"
                >
                  {Icon && <Icon className="w-4 h-4" />}
                  {item.label}
                </Link>
              ) : (
                <span
                  className={clsx(
                    "flex items-center gap-1",
                    isLast && "text-gray-900 font-semibold"
                  )}
                >
                  {Icon && <Icon className="w-4 h-4" />}
                  {item.label}
                </span>
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
};
