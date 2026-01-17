// config/roleNavigation.ts
import { Home, Settings, CreditCard, FileText, Calendar, Users } from "lucide-react";
import { UserRole } from "@/types";

export const roleDashboardMap: Record<UserRole, {
  label: string;
  path: string;
  icon: React.ElementType;
}> = {
  parent: {
    label: "Dashboard",
    path: "/dashboard",
    icon: Home,
  },
  child: {
    label: "Dashboard",
    path: "/child-dashboard",
    icon: Home,
  },
  teacher: {
    label: "Dashboard",
    path: "/teacher-dashboard",
    icon: Home,
  },
};

export const parentNavigation: Array<{
label: string;
path: string;
icon: React.ElementType;
}> = [
{
  label: "Dashboard",
  path: "/dashboard",
  icon: Home,
},
{
  label: "Children",
  path: "/children",
  icon: Users,
},
{
  label: "Assessment Reports",
  path: "/assessment-reports",
  icon: FileText,
},
{
  label: "Schedule & Progress",
  path: "/child-schedule",
  icon: Calendar,
},
{
  label: "Billing",
  path: "/parent-settings?tab=billing",
  icon: CreditCard,
},
{
  label: "Settings",
  path: "/parent-settings",
  icon: Settings,
},
];
