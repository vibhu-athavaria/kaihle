import {
  BrowserRouter,
  Routes,
  Route,
  Navigate,
  useRoutes,
} from "react-router-dom";
import { PrivateRoute, RoleRoute, useAuth } from "@kaihle/auth";
import { UserRole } from "@kaihle/types";
import { LoginPage } from "./pages/LoginPage";
import { DashboardLayout, ErrorBoundary } from "@kaihle/ui";
import { TeacherDashboard } from "./pages/dashboard/TeacherDashboard";
import { TeacherSettingsPage } from "./pages/settings/TeacherSettingsPage";
import { NewAssessmentPage } from "./pages/assessments/NewAssessmentPage";
import { AssessmentListPage } from "./pages/assessments/AssessmentListPage";
import { Link } from "react-router-dom";
import { Button } from "@kaihle/ui";
import { Plus } from "lucide-react";

function TeacherShell() {
  const { user, logout } = useAuth();

  const greeting = () => {
    const hour = new Date().getHours();
    if (hour < 12) return "Good morning";
    if (hour < 18) return "Good afternoon";
    return "Good evening";
  };

  const teacherName = user?.email?.split("@")[0] || "Teacher";

  // Inner routes rendered inside the DashboardLayout
  const innerRoutes = useRoutes([
    { path: "dashboard", element: <TeacherDashboard /> },
    { path: "assessments/new", element: <NewAssessmentPage /> },
    {
      path: "classes/:classId/assessments",
      element: <AssessmentListPage />,
    },
    // Default: redirect to dashboard
    { path: "*", element: <Navigate to="/teacher/dashboard" replace /> },
  ]);

  return (
    <DashboardLayout
      variant="teacher"
      pageTitle={`${greeting()}, ${teacherName}`}
      onLogout={logout}
      topNavAction={
        <Link to="/teacher/assessments/new">
          <Button
            variant="primary"
            size="sm"
            className="gap-1 bg-brand-gold hover:bg-brand-gold-dark"
          >
            <Plus className="w-4 h-4" aria-hidden="true" />
            Assessment
          </Button>
        </Link>
      }
    >
      {innerRoutes}
    </DashboardLayout>
  );
}

function TeacherSettingsApp() {
  const { logout } = useAuth();

  return (
    <DashboardLayout variant="teacher" pageTitle="Settings" onLogout={logout}>
      <TeacherSettingsPage />
    </DashboardLayout>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route
          path="/teacher/settings"
          element={
            <PrivateRoute>
              <RoleRoute allowedRoles={[UserRole.TEACHER]}>
                <ErrorBoundary role="teacher">
                  <TeacherSettingsApp />
                </ErrorBoundary>
              </RoleRoute>
            </PrivateRoute>
          }
        />
        <Route
          path="/teacher/*"
          element={
            <PrivateRoute>
              <RoleRoute
                allowedRoles={[
                  UserRole.TEACHER,
                  UserRole.SCHOOL_ADMIN,
                  UserRole.KAIHLE_ADMIN,
                ]}
              >
                <ErrorBoundary role="teacher">
                  <TeacherShell />
                </ErrorBoundary>
              </RoleRoute>
            </PrivateRoute>
          }
        />
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
