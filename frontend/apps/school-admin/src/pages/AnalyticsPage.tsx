import { DashboardLayout } from "@kaihle/ui";
import { Card } from "@kaihle/ui";
import { TrendingUp, Users, GraduationCap, UserCog } from "lucide-react";
import { useAuth } from "@kaihle/auth";
import { useSchoolAnalytics } from "../hooks/useSchoolAdmin";

export function AnalyticsPage() {
  const { logout } = useAuth();
  const { data: analytics, isLoading } = useSchoolAnalytics();

  if (isLoading) {
    return (
      <DashboardLayout
        variant="school-admin"
        pageTitle="Analytics"
        onLogout={logout}
      >
        <div className="flex items-center justify-center h-64">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-primary"></div>
        </div>
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout
      variant="school-admin"
      pageTitle="Analytics"
      onLogout={logout}
    >
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold font-display text-gray-900">
            Analytics
          </h1>
          <p className="text-gray-600 mt-1">
            Track your school&apos;s performance metrics
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          <Card className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">Total Teachers</p>
                <p className="text-2xl font-bold text-gray-900 mt-1">
                  {analytics?.teacher_count ?? 0}
                </p>
              </div>
              <div className="p-3 bg-brand-green/10 rounded-full">
                <Users className="w-6 h-6 text-brand-green" />
              </div>
            </div>
          </Card>

          <Card className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">Total Students</p>
                <p className="text-2xl font-bold text-gray-900 mt-1">
                  {analytics?.student_count ?? 0}
                </p>
              </div>
              <div className="p-3 bg-brand-green/10 rounded-full">
                <GraduationCap className="w-6 h-6 text-brand-green" />
              </div>
            </div>
          </Card>

          <Card className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">Total Parents</p>
                <p className="text-2xl font-bold text-gray-900 mt-1">
                  {analytics?.parent_count ?? 0}
                </p>
              </div>
              <div className="p-3 bg-brand-green/10 rounded-full">
                <UserCog className="w-6 h-6 text-brand-green" />
              </div>
            </div>
          </Card>

          <Card className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">Onboarding Rate</p>
                <p className="text-2xl font-bold text-gray-900 mt-1">
                  {analytics?.onboarding_percentage ?? 0}%
                </p>
              </div>
              <div className="p-3 bg-brand-green/10 rounded-full">
                <TrendingUp className="w-6 h-6 text-brand-green" />
              </div>
            </div>
          </Card>
        </div>

        <Card className="p-6">
          <h2 className="text-lg font-semibold font-display text-gray-900 mb-4">
            Performance Overview
          </h2>
          <div className="h-64 flex items-center justify-center text-gray-400">
            <p>Detailed analytics charts coming soon</p>
          </div>
        </Card>
      </div>
    </DashboardLayout>
  );
}
