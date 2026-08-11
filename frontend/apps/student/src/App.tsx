import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import {
  PrivateRoute,
  RoleRoute,
  OnboardingRoute,
  ResetPasswordRoute,
  ForgotPasswordRoute,
  ImpersonateRoute,
  ImpersonationBar,
  useAuthStore,
} from "@kaihle/auth";
import { UserRole } from "@kaihle/types";
import { ErrorBoundary } from "@kaihle/ui";
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
import { DiagnosticStartPage } from "./pages/assessments/DiagnosticStartPage";
import { AssessmentResultsPage } from "./pages/assessments/AssessmentResultsPage";
import { StudyPlanDetail } from "./pages/study-plans/StudyPlanDetail";
import { ClassTopicsPage } from "./pages/classes/ClassTopicsPage";
import { ClassPage } from "./pages/classes/ClassPage";
import { TopicDetailPage } from "./pages/topics/TopicDetailPage";
import { MiniCoursePage } from "./pages/mini-course/MiniCoursePage";

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

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/forgot-password" element={<ForgotPasswordRoute />} />
        <Route path="/reset-password" element={<ResetPasswordRoute />} />
        <Route
          path="/impersonate"
          element={<ImpersonateRoute homePath="/student/dashboard" />}
        />
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
              <OnboardingRoute>
                <ErrorBoundary role="student">
                  <StudentDashboard />
                </ErrorBoundary>
              </OnboardingRoute>
            </PrivateRouteWithPasswordCheck>
          }
        />
        <Route
          path="/student/classes/:classId/diagnostic"
          element={
            <PrivateRouteWithPasswordCheck>
              <OnboardingRoute>
                <ErrorBoundary role="student">
                  <DiagnosticStartPage />
                </ErrorBoundary>
              </OnboardingRoute>
            </PrivateRouteWithPasswordCheck>
          }
        />
        <Route
          path="/student/classes/:classId"
          element={
            <PrivateRouteWithPasswordCheck>
              <OnboardingRoute>
                <ErrorBoundary role="student">
                  <ClassPage />
                </ErrorBoundary>
              </OnboardingRoute>
            </PrivateRouteWithPasswordCheck>
          }
        />
        <Route
          path="/student/classes/:classId/topics"
          element={
            <PrivateRouteWithPasswordCheck>
              <OnboardingRoute>
                <ErrorBoundary role="student">
                  <ClassTopicsPage />
                </ErrorBoundary>
              </OnboardingRoute>
            </PrivateRouteWithPasswordCheck>
          }
        />
        <Route
          path="/student/classes/:classId/topics/:topicId"
          element={
            <PrivateRouteWithPasswordCheck>
              <OnboardingRoute>
                <ErrorBoundary role="student">
                  <TopicDetailPage />
                </ErrorBoundary>
              </OnboardingRoute>
            </PrivateRouteWithPasswordCheck>
          }
        />
        <Route
          path="/student/subtopics/:subtopicId/course"
          element={
            <PrivateRouteWithPasswordCheck>
              <OnboardingRoute>
                <ErrorBoundary role="student">
                  <MiniCoursePage />
                </ErrorBoundary>
              </OnboardingRoute>
            </PrivateRouteWithPasswordCheck>
          }
        />
        <Route
          path="/student/my-progress"
          element={
            <PrivateRouteWithPasswordCheck>
              <OnboardingRoute>
                <ErrorBoundary role="student">
                  <MyProgress />
                </ErrorBoundary>
              </OnboardingRoute>
            </PrivateRouteWithPasswordCheck>
          }
        />
        <Route
          path="/student/study-plans"
          element={
            <PrivateRouteWithPasswordCheck>
              <OnboardingRoute>
                <ErrorBoundary role="student">
                  <StudyPlans />
                </ErrorBoundary>
              </OnboardingRoute>
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
              <OnboardingRoute>
                <ErrorBoundary role="student">
                  <Assessments />
                </ErrorBoundary>
              </OnboardingRoute>
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
              <OnboardingRoute>
                <RoleRoute allowedRoles={[UserRole.STUDENT]}>
                  <StudentSettings />
                </RoleRoute>
              </OnboardingRoute>
            </PrivateRouteWithPasswordCheck>
          }
        />
        <Route
          path="/student/*"
          element={
            <PrivateRouteWithPasswordCheck>
              <OnboardingRoute>
                <ErrorBoundary role="student">
                  <StudentDashboard />
                </ErrorBoundary>
              </OnboardingRoute>
            </PrivateRouteWithPasswordCheck>
          }
        />
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
      <ImpersonationBar />
    </BrowserRouter>
  );
}
