import {
  BrowserRouter,
  Routes,
  Route,
  Navigate,
  useSearchParams,
  useNavigate,
} from "react-router-dom";
import {
  PrivateRoute,
  RoleRoute,
  OnboardingRoute,
  useAuthStore,
  apiClient,
} from "@kaihle/auth";
import { UserRole } from "@kaihle/types";
import {
  ErrorBoundary,
  ForgotPasswordPage,
  ResetPasswordPage,
} from "@kaihle/ui";
import { LoginPage } from "./pages/LoginPage";
import { ChangePasswordPage } from "./pages/ChangePasswordPage";
import { OnboardingRouter } from "./pages/onboarding/OnboardingRouter";
import { ProfileQuestionnaire } from "./pages/onboarding/ProfileQuestionnaire";
import { StudentDashboard } from "./pages/dashboard/StudentDashboard";
import { MyProgress } from "./pages/my-progress/MyProgress";
import { StudyPlans } from "./pages/study-plans/StudyPlans";
import { Assessments } from "./pages/assessments/Assessments";
import { StudentSettings } from "./pages/settings/StudentSettings";
import { TakeAssessmentPage } from "./pages/assessments/TakeAssessmentPage";
import { AssessmentResultsPage } from "./pages/assessments/AssessmentResultsPage";
import { StudyPlanDetail } from "./pages/study-plans/StudyPlanDetail";

function PrivateRouteWithPasswordCheck({
  children,
}: {
  children: React.ReactNode;
}) {
  const mustChangePassword = useAuthStore((state) => state.mustChangePassword);
  return (
    <PrivateRoute>
      {mustChangePassword ? (
        <Navigate to="/student/change-password" replace />
      ) : (
        children
      )}
    </PrivateRoute>
  );
}

function ResetPasswordRoute() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  return (
    <ResetPasswordPage
      token={searchParams.get("token") ?? ""}
      onReset={(token, password) =>
        apiClient.post("/api/v1/auth/reset-password", {
          token,
          password,
          confirm_password: password,
        })
      }
      onSuccess={() => navigate("/login", { replace: true })}
      appLoginPath="/login"
      forgotPasswordPath="/forgot-password"
    />
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route
          path="/forgot-password"
          element={
            <ForgotPasswordPage
              onSubmit={(email) =>
                apiClient.post("/api/v1/auth/forgot-password", { email })
              }
              appLoginPath="/login"
            />
          }
        />
        <Route path="/reset-password" element={<ResetPasswordRoute />} />
        <Route
          path="/student/change-password"
          element={
            <PrivateRoute>
              <ChangePasswordPage />
            </PrivateRoute>
          }
        />
        <Route
          path="/student/onboarding"
          element={
            <PrivateRouteWithPasswordCheck>
              <OnboardingRouter />
            </PrivateRouteWithPasswordCheck>
          }
        />
        <Route
          path="/student/onboarding/profile"
          element={
            <PrivateRouteWithPasswordCheck>
              <ProfileQuestionnaire />
            </PrivateRouteWithPasswordCheck>
          }
        />
        <Route
          path="/student/dashboard"
          element={
            <PrivateRouteWithPasswordCheck>
              <ErrorBoundary role="student">
                <StudentDashboard />
              </ErrorBoundary>
            </PrivateRouteWithPasswordCheck>
          }
        />
        <Route
          path="/student/my-progress"
          element={
            <PrivateRouteWithPasswordCheck>
              <ErrorBoundary role="student">
                <MyProgress />
              </ErrorBoundary>
            </PrivateRouteWithPasswordCheck>
          }
        />
        <Route
          path="/student/study-plans"
          element={
            <PrivateRouteWithPasswordCheck>
              <ErrorBoundary role="student">
                <StudyPlans />
              </ErrorBoundary>
            </PrivateRouteWithPasswordCheck>
          }
        />
        <Route
          path="/student/study-plans/:planId"
          element={
            <PrivateRouteWithPasswordCheck>
              <OnboardingRoute>
                <ErrorBoundary role="student">
                  <StudyPlanDetail />
                </ErrorBoundary>
              </OnboardingRoute>
            </PrivateRouteWithPasswordCheck>
          }
        />
        <Route
          path="/student/assessments"
          element={
            <PrivateRouteWithPasswordCheck>
              <ErrorBoundary role="student">
                <Assessments />
              </ErrorBoundary>
            </PrivateRouteWithPasswordCheck>
          }
        />
        <Route
          path="/student/assessments/:attemptId/take"
          element={
            <PrivateRouteWithPasswordCheck>
              <OnboardingRoute>
                <ErrorBoundary role="student">
                  <TakeAssessmentPage />
                </ErrorBoundary>
              </OnboardingRoute>
            </PrivateRouteWithPasswordCheck>
          }
        />
        <Route
          path="/student/assessments/:attemptId/results"
          element={
            <PrivateRouteWithPasswordCheck>
              <OnboardingRoute>
                <ErrorBoundary role="student">
                  <AssessmentResultsPage />
                </ErrorBoundary>
              </OnboardingRoute>
            </PrivateRouteWithPasswordCheck>
          }
        />
        <Route
          path="/student/settings"
          element={
            <PrivateRouteWithPasswordCheck>
              <RoleRoute allowedRoles={[UserRole.STUDENT]}>
                <StudentSettings />
              </RoleRoute>
            </PrivateRouteWithPasswordCheck>
          }
        />
        {/* Catch-all for any unmatched /student/* routes - redirect to dashboard */}
        <Route
          path="/student/*"
          element={
            <PrivateRouteWithPasswordCheck>
              <ErrorBoundary role="student">
                <StudentDashboard />
              </ErrorBoundary>
            </PrivateRouteWithPasswordCheck>
          }
        />
        {/* ADD THIS */}
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
