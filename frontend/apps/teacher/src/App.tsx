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
import { AllAssessmentsPage } from "./pages/assessments/AllAssessmentsPage";
import { AllAssessmentsPage } from "./pages/assessments/AllAssessmentsPage";
import { ClassesPage } from "./pages/classes/ClassesPage";
import { ClassDetailPage } from "./pages/classes/ClassDetailPage";
import { GapMapPage } from "./pages/gap-map/GapMapPage";
import { MyStudentsPage } from "./pages/MyStudents";
import { StudentProfilePage } from "./pages/StudentProfilePage";
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
      { path: "classes", element: <ClassesPage /> },
      { path: "students", element: <MyStudentsPage /> },
      { path: "assessments", element: <AllAssessmentsPage /> },
      { path: "assessments", element: <AllAssessmentsPage /> },
      {
        path: "students/:studentId/profile",
        element: <StudentProfilePage />,
      },
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
      { path: "", element: <ClassDetailPage /> },
      { path: "gap-map", element: <GapMapPage /> },
      { path: "assessments", element: <AssessmentListPage /> },
      {
        path: "explanation-review",
        element: <ExplanationReviewPage />,
      },
      // T-002: { path: "study-plan", element: <StudyPlanPage /> },
      // T-002: { path: "lesson-plans", element: <LessonPlansPage /> },
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

function NewAssessmentApp() {
  const { user, logout } = useAuth();

  const greeting = () => {
    const hour = new Date().getHours();
    if (hour < 12) return "Good morning";
    if (hour < 18) return "Good afternoon";
    return "Good evening";
  };

  const teacherName = user?.email?.split("@")[0] || "Teacher";

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
      <NewAssessmentPage />
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
          path="/teacher/assessments/new"
          element={
            <PrivateRoute>
              <RoleRoute allowedRoles={[UserRole.TEACHER]}>
                <ErrorBoundary role="teacher">
                  <NewAssessmentApp />
                </ErrorBoundary>
              </RoleRoute>
            </PrivateRoute>
          }
        />
        <Route
          path="/teacher/classes/:classId/*"
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
