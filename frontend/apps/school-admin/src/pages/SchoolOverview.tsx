import { Link } from "react-router-dom";
import { DashboardLayout } from "@kaihle/ui";
import { Card } from "@kaihle/ui";
import { Button } from "@kaihle/ui";
import { useAuth } from "@kaihle/auth";
import { Users, GraduationCap, TrendingUp, Plus } from "lucide-react";
import { useSchoolAnalytics, useSchoolClasses } from "../hooks/useSchoolAdmin";

export function SchoolOverview() {
  const { logout } = useAuth();
  const { data: analytics, isLoading: analyticsLoading } = useSchoolAnalytics();
  const { data: classes, isLoading: classesLoading } = useSchoolClasses();

  const kpis = [
    {
      label: "Teachers",
      value: analytics?.teacher_count ?? 0,
      icon: Users,
      color: "text-brand-primary",
    },
    {
      label: "Students",
      value: analytics?.student_count ?? 0,
      icon: GraduationCap,
      color: "text-brand-primary",
    },
    {
      label: "Onboarding",
      value: `${analytics?.onboarding_percentage ?? 0}%`,
      icon: TrendingUp,
      color: "text-brand-green",
    },
  ];

  return (
    <DashboardLayout
      variant="school-admin"
      pageTitle="Overview"
      pageSubtitle="Welcome back! Here's what's happening at your school."
      onLogout={logout}
    >
      <div className="space-y-6">
        <section>
          <h2 className="text-lg font-display font-bold text-brand-ink mb-4">
            Quick stats
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {kpis.map((kpi) => (
              <Card
                key={kpi.label}
                variant="default"
                className="bg-white border-role-school-border"
              >
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-brand-body">{kpi.label}</p>
                    <p className="text-3xl font-display font-bold text-brand-ink mt-1">
                      {analyticsLoading ? "..." : kpi.value}
                    </p>
                  </div>
                  <div
                    className={`p-3 rounded-full bg-brand-light ${kpi.color}`}
                  >
                    <kpi.icon className="w-6 h-6" />
                  </div>
                </div>
              </Card>
            ))}
          </div>
        </section>

        <section>
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-display font-bold text-brand-ink">
              Classes
            </h2>
            <Link to="/school-admin/classes">
              <Button variant="primary" size="sm">
                <Plus className="w-4 h-4 mr-1" />
                Create class
              </Button>
            </Link>
          </div>
          <Card
            variant="default"
            className="bg-white border-role-school-border overflow-hidden"
          >
            {classesLoading ? (
              <div className="p-8 text-center text-brand-muted">Loading...</div>
            ) : classes && classes.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="border-b border-brand-border text-left">
                      <th className="py-3 px-4 text-xs font-bold uppercase text-brand-muted">
                        Class
                      </th>
                      <th className="py-3 px-4 text-xs font-bold uppercase text-brand-muted">
                        Teacher
                      </th>
                      <th className="py-3 px-4 text-xs font-bold uppercase text-brand-muted">
                        Students
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {classes.slice(0, 10).map((cls) => (
                      <tr
                        key={cls.id}
                        className="border-b border-brand-border-soft last:border-0 hover:bg-brand-light/30"
                      >
                        <td className="py-3 px-4 text-sm font-medium text-brand-ink">
                          {cls.name}
                        </td>
                        <td className="py-3 px-4 text-sm text-brand-body">
                          {cls.teacher_name || "Unassigned"}
                        </td>
                        <td className="py-3 px-4 text-sm text-brand-body">
                          {cls.student_count}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {classes.length > 10 && (
                  <div className="p-3 text-center border-t border-brand-border">
                    <Link
                      to="/school-admin/classes"
                      className="text-sm text-brand-primary hover:underline"
                    >
                      View all {classes.length} classes →
                    </Link>
                  </div>
                )}
              </div>
            ) : (
              <div className="p-8 text-center text-brand-muted">
                No classes yet. Create your first class to get started.
              </div>
            )}
          </Card>
        </section>

        <section>
          <h2 className="text-lg font-display font-bold text-brand-ink mb-4">
            Onboarding progress
          </h2>
          <Card
            variant="highlighted"
            className="bg-brand-light border-role-school-border"
          >
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm text-brand-body">
                {analytics?.onboarded_students ?? 0} of{" "}
                {analytics?.total_students ?? 0} students fully onboarded
              </span>
              <span className="text-sm font-bold text-brand-primary">
                {analytics?.onboarding_percentage ?? 0}%
              </span>
            </div>
            <div className="w-full bg-white rounded-full h-3">
              <div
                className="bg-brand-primary h-3 rounded-full transition-all duration-500"
                style={{ width: `${analytics?.onboarding_percentage ?? 0}%` }}
                role="progressbar"
                aria-valuenow={analytics?.onboarding_percentage ?? 0}
                aria-valuemin={0}
                aria-valuemax={100}
              />
            </div>
            <div className="mt-4 text-right">
              <Link
                to="/school-admin/analytics"
                className="text-sm text-brand-primary hover:underline font-medium"
              >
                View analytics →
              </Link>
            </div>
          </Card>
        </section>
      </div>
    </DashboardLayout>
  );
}
