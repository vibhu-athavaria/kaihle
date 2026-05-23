import {
  BrowserRouter,
  Routes,
  Route,
  Navigate,
  useRoutes,
} from "react-router-dom";
import { useMemo } from "react";
import {
  PrivateRoute,
  RoleRoute,
  ResetPasswordRoute,
  ForgotPasswordRoute,
  useAuth,
  useAuthStore,
} from "@kaihle/auth";
import { UserRole } from "@kaihle/types";
import { LoginPage } from "./pages/LoginPage";
import { ChangePasswordPage } from "./pages/ChangePasswordPage";
import { DashboardLayout, ErrorBoundary } from "@kaihle/ui";
import { TeacherDashboard } from "./pages/dashboard/TeacherDashboard";
import { TeacherSettingsPage } from "./pages/settings/TeacherSettingsPage";
import { NewAssessmentPage } from "./pages/assessments/NewAssessmentPage";
import { AssessmentListPage } from "./pages/assessments/AssessmentListPage";
import { AssessmentResultsPage } from "./pages/assessments/AssessmentResultsPage";
import { StudentResultDetailPage } from "./pages/assessments/StudentResultDetailPage";
import { ExplanationReviewPage } from "./pages/classes/ExplanationReviewPage";
import { AllAssessmentsPage } from "./pages/assessments/AllAssessmentsPage";
import { ClassesPage } from "./pages/classes/ClassesPage";
import { ClassDetailPage } from "./pages/classes/ClassDetailPage";
import { GapMapPage } from "./pages/gap-map/GapMapPage";
import { MyStudentsPage } from "./pages/MyStudents";
import { StudentProfilePage } from "./pages/StudentProfilePage";
import { AllLessonPlansPage } from "./pages/lesson-plans/AllLessonPlansPage";
import { LessonPlanDetailPage } from "./pages/lesson-plans/LessonPlanDetailPage";
import { TeacherLessonPlansPage } from "./pages/lesson-plans/TeacherLessonPlansPage";
import { ContentReviewPage } from "./pages/content-review/ContentReviewPage";
import { CourseDetailPage } from "./pages/content-review/CourseDetailPage";
import { ClassStudyPlanPage } from "./pages/classes/ClassStudyPlanPage";
import { SubtopicContentBrowser } from "./pages/SubtopicContentBrowser";

// Plain function — no state, no effects, no React APIs
function getTeacherGreeting(firstName: string | undefined): {
  pageTitle: string;
} {
  const hour = new Date().getHours();
  const greeting =
    hour < 12 ? "Good morning" : hour < 18 ? "Good afternoon" : "Good evening";
  const name = firstName || "Teacher";
  return { pageTitle: `${greeting}, ${name}` };
}

function TeacherShell() {
  const { user, logout } = useAuth();
  const { pageTitle } = getTeacherGreeting(user?.first_name);

  const routes = useMemo(
    () => [
      { path: "dashboard", element: <TeacherDashboard /> },
      { path: "classes", element: <ClassesPage /> },
      { path: "students", element: <MyStudentsPage /> },
      { path: "assessments", element: <AllAssessmentsPage /> },
      { path: "lesson-plans", element: <TeacherLessonPlansPage /> },
      { path: "content-review", element: <ContentReviewPage /> },
      {
        path: "content-review/mini-courses/:topicId",
        element: <CourseDetailPage />,
      },
      {
        path: "students/:studentId/profile",
        element: <StudentProfilePage />,
      },
      { path: "*", element: <Navigate to="/teacher/dashboard" replace /> },
    ],
    [],
  );
  const innerRoutes = useRoutes(routes);

  return (
    <DashboardLayout variant="teacher" pageTitle={pageTitle} onLogout={logout}>
      {innerRoutes}
    </DashboardLayout>
  );
}

function TeacherContentShell() {
  const { user, logout } = useAuth();
  const { pageTitle } = getTeacherGreeting(user?.first_name);

  const contentRoutes = useMemo(
    () => [
      { path: "", element: <ClassDetailPage /> },
      { path: "gap-map", element: <GapMapPage /> },
      { path: "assessments", element: <AssessmentListPage /> },
      { path: "study-plan", element: <ClassStudyPlanPage /> },
      { path: "lesson-plans", element: <AllLessonPlansPage /> },
      { path: "lesson-plans/:planId", element: <LessonPlanDetailPage /> },
      {
        path: "explanation-review",
        element: <ExplanationReviewPage />,
      },
      {
        path: "subtopics/:subtopicId/content",
        element: <SubtopicContentBrowser />,
      },
      { path: "*", element: <Navigate to="/teacher/dashboard" replace /> },
    ],
    [],
  );
  const innerRoutes = useRoutes(contentRoutes);

  return (
    <DashboardLayout variant="teacher" pageTitle={pageTitle} onLogout={logout}>
      {innerRoutes}
    </DashboardLayout>
  );
}

function TeacherSettingsApp() {
  const { user, logout } = useAuth();
  const { pageTitle } = getTeacherGreeting(user?.first_name);

  return (
    <DashboardLayout variant="teacher" pageTitle={pageTitle} onLogout={logout}>
      <TeacherSettingsPage />
    </DashboardLayout>
  );
}

function NewAssessmentApp() {
  const { user, logout } = useAuth();
  const { pageTitle } = getTeacherGreeting(user?.first_name);

  return (
    <DashboardLayout variant="teacher" pageTitle={pageTitle} onLogout={logout}>
      <NewAssessmentPage />
    </DashboardLayout>
  );
}

function PrivateRouteWithPasswordCheck({
  children,
}: {
  children: React.ReactNode;
}) {
  const mustChangePassword = useAuthStore((state) => state.mustChangePassword);
  return (
    <PrivateRoute>
      {mustChangePassword ? (
        <Navigate to="/teacher/change-password" replace />
      ) : (
        children
      )}
    </PrivateRoute>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/forgot-password" element={<ForgotPasswordRoute />} />
        <Route path="/reset-password" element={<ResetPasswordRoute />} />
        <Route
          path="/teacher/change-password"
          element={
            <PrivateRoute>
              <ChangePasswordPage />
            </PrivateRoute>
          }
        />
        <Route
          path="/teacher/settings"
          element={
            <PrivateRouteWithPasswordCheck>
              <RoleRoute
                allowedRoles={[
                  UserRole.TEACHER,
                  UserRole.SCHOOL_ADMIN,
                  UserRole.KAIHLE_ADMIN,
                ]}
              >
                <ErrorBoundary role="teacher">
                  <TeacherSettingsApp />
                </ErrorBoundary>
              </RoleRoute>
            </PrivateRouteWithPasswordCheck>
          }
        />
        <Route
          path="/teacher/assessments/new"
          element={
            <PrivateRouteWithPasswordCheck>
              <RoleRoute
                allowedRoles={[
                  UserRole.TEACHER,
                  UserRole.SCHOOL_ADMIN,
                  UserRole.KAIHLE_ADMIN,
                ]}
              >
                <ErrorBoundary role="teacher">
                  <NewAssessmentApp />
                </ErrorBoundary>
              </RoleRoute>
            </PrivateRouteWithPasswordCheck>
          }
        />
        <Route
          path="/teacher/classes/:classId/*"
          element={
            <PrivateRouteWithPasswordCheck>
              <RoleRoute
                allowedRoles={[
                  UserRole.TEACHER,
                  UserRole.SCHOOL_ADMIN,
                  UserRole.KAIHLE_ADMIN,
                ]}
              >
                <ErrorBoundary role="teacher">
                  <TeacherContentShell />
                </ErrorBoundary>
              </RoleRoute>
            </PrivateRouteWithPasswordCheck>
          }
        />
        <Route
          path="/teacher/assessments/:assessmentId/results/:studentId"
          element={
            <PrivateRouteWithPasswordCheck>
              <RoleRoute
                allowedRoles={[
                  UserRole.TEACHER,
                  UserRole.SCHOOL_ADMIN,
                  UserRole.KAIHLE_ADMIN,
                ]}
              >
                <ErrorBoundary role="teacher">
                  <StudentResultDetailPage />
                </ErrorBoundary>
              </RoleRoute>
            </PrivateRouteWithPasswordCheck>
          }
        />
        <Route
          path="/teacher/assessments/:assessmentId/results"
          element={
            <PrivateRouteWithPasswordCheck>
              <RoleRoute
                allowedRoles={[
                  UserRole.TEACHER,
                  UserRole.SCHOOL_ADMIN,
                  UserRole.KAIHLE_ADMIN,
                ]}
              >
                <ErrorBoundary role="teacher">
                  <AssessmentResultsPage />
                </ErrorBoundary>
              </RoleRoute>
            </PrivateRouteWithPasswordCheck>
          }
        />
        <Route
          path="/teacher/*"
          element={
            <PrivateRouteWithPasswordCheck>
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
            </PrivateRouteWithPasswordCheck>
          }
        />
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
