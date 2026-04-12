import {
  BrowserRouter,
  Routes,
  Route,
  Navigate,
  useRoutes,
} from "react-router-dom";
import { useMemo } from "react";
import { PrivateRoute, RoleRoute, useAuth } from "@kaihle/auth";
import { UserRole } from "@kaihle/types";
import { LoginPage } from "./pages/LoginPage";
import { DashboardLayout, ErrorBoundary } from "@kaihle/ui";
import { TeacherDashboard } from "./pages/dashboard/TeacherDashboard";
import { TeacherSettingsPage } from "./pages/settings/TeacherSettingsPage";
import { NewAssessmentPage } from "./pages/assessments/NewAssessmentPage";
import { AssessmentListPage } from "./pages/assessments/AssessmentListPage";
import { AssessmentResultsPage } from "./pages/assessments/AssessmentResultsPage";
import { StudentResultDetailPage } from "./pages/assessments/StudentResultDetailPage";
import { ExplanationReviewPage } from "./pages/classes/ExplanationReviewPage";
import { GapMapPage } from "./pages/gap-map/GapMapPage";
import { StudentProfilePage } from "./pages/StudentProfilePage";
import { LessonPlansPage } from "./pages/lesson-plans/LessonPlansPage";
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
  const routes = useMemo(
    () => [
      { path: "dashboard", element: <TeacherDashboard /> },
      // Default: redirect to dashboard
      { path: "*", element: <Navigate to="/teacher/dashboard" replace /> },
    ],
    [],
  );
  const innerRoutes = useRoutes(routes);

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

// Shell for assessment-specific routes — TEACHER only (no admin impersonation)
function TeacherAssessmentShell() {
  const { user, logout } = useAuth();

  const greeting = () => {
    const hour = new Date().getHours();
    if (hour < 12) return "Good morning";
    if (hour < 18) return "Good afternoon";
    return "Good evening";
  };

  const teacherName = user?.email?.split("@")[0] || "Teacher";

  const assessmentRoutes = useMemo(
    () => [
      { path: "assessments/new", element: <NewAssessmentPage /> },
      {
        path: "classes/:classId/assessments",
        element: <AssessmentListPage />,
      },
      { path: "*", element: <Navigate to="/teacher/dashboard" replace /> },
    ],
    [],
  );
  const innerRoutes = useRoutes(assessmentRoutes);

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

// Shell for class-specific content routes — TEACHER only
function TeacherContentShell() {
  const { user, logout } = useAuth();

  const greeting = () => {
    const hour = new Date().getHours();
    if (hour < 12) return "Good morning";
    if (hour < 18) return "Good afternoon";
    return "Good evening";
  };

  const teacherName = user?.email?.split("@")[0] || "Teacher";

  const contentRoutes = useMemo(
    () => [
      {
        path: "classes/:classId/explanation-review",
        element: <ExplanationReviewPage />,
      },
      {
        path: "classes/:classId/gap-map",
        element: <GapMapPage />,
      },
      {
        path: "classes/:classId/lesson-plans",
        element: <LessonPlansPage />,
      },
      { path: "*", element: <Navigate to="/teacher/dashboard" replace /> },
    ],
    [],
  );
  const innerRoutes = useRoutes(contentRoutes);

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
        {/* Assessment creation/management routes — TEACHER only */}
        <Route
          path="/teacher/assessments/new"
          element={
            <PrivateRoute>
              <RoleRoute allowedRoles={[UserRole.TEACHER]}>
                <ErrorBoundary role="teacher">
                  <TeacherAssessmentShell />
                </ErrorBoundary>
              </RoleRoute>
            </PrivateRoute>
          }
        />
        <Route
          path="/teacher/classes/:classId/assessments"
          element={
            <PrivateRoute>
              <RoleRoute allowedRoles={[UserRole.TEACHER]}>
                <ErrorBoundary role="teacher">
                  <TeacherAssessmentShell />
                </ErrorBoundary>
              </RoleRoute>
            </PrivateRoute>
          }
        />
        {/* Class content review routes — TEACHER only */}
        <Route
          path="/teacher/classes/:classId/explanation-review"
          element={
            <PrivateRoute>
              <RoleRoute allowedRoles={[UserRole.TEACHER]}>
                <ErrorBoundary role="teacher">
                  <TeacherContentShell />
                </ErrorBoundary>
              </RoleRoute>
            </PrivateRoute>
          }
        />
        <Route
          path="/teacher/classes/:classId/gap-map"
          element={
            <PrivateRoute>
              <RoleRoute allowedRoles={[UserRole.TEACHER]}>
                <ErrorBoundary role="teacher">
                  <TeacherContentShell />
                </ErrorBoundary>
              </RoleRoute>
            </PrivateRoute>
          }
        />
        <Route
          path="/teacher/classes/:classId/lesson-plans"
          element={
            <PrivateRoute>
              <RoleRoute allowedRoles={[UserRole.TEACHER]}>
                <ErrorBoundary role="teacher">
                  <TeacherContentShell />
                </ErrorBoundary>
              </RoleRoute>
            </PrivateRoute>
          }
        />
        {/* Assessment results routes — standalone (no shell needed, pages provide own layout) */}
        <Route
          path="/teacher/assessments/:assessmentId/results"
          element={
            <PrivateRoute>
              <RoleRoute allowedRoles={[UserRole.TEACHER]}>
                <ErrorBoundary role="teacher">
                  <AssessmentResultsPage />
                </ErrorBoundary>
              </RoleRoute>
            </PrivateRoute>
          }
        />
        <Route
          path="/teacher/assessments/:assessmentId/results/:studentId"
          element={
            <PrivateRoute>
              <RoleRoute allowedRoles={[UserRole.TEACHER]}>
                <ErrorBoundary role="teacher">
                  <StudentResultDetailPage />
                </ErrorBoundary>
              </RoleRoute>
            </PrivateRoute>
          }
        />
        {/* Student profile route — TEACHER only */}
        <Route
          path="/teacher/students/:studentId/profile"
          element={
            <PrivateRoute>
              <RoleRoute allowedRoles={[UserRole.TEACHER]}>
                <ErrorBoundary role="teacher">
                  <StudentProfilePage />
                </ErrorBoundary>
              </RoleRoute>
            </PrivateRoute>
          }
        />
        {/* General teacher shell — admins may also view teacher dashboard */}
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
