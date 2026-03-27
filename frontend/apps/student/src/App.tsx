import { BrowserRouter, Routes, Route } from "react-router-dom";
import { PrivateRoute, RoleRoute } from "@kaihle/auth";
import { UserRole } from "@kaihle/types";
import { ErrorBoundary } from "@kaihle/ui";
import { LoginPage } from "./pages/LoginPage";
import { OnboardingRouter } from "./pages/onboarding/OnboardingRouter";
import { ProfileQuestionnaire } from "./pages/onboarding/ProfileQuestionnaire";
import { StudentDashboard } from "./pages/dashboard/StudentDashboard";
import { MyProgress } from "./pages/my-progress/MyProgress";
import { StudyPlans } from "./pages/study-plans/StudyPlans";
import { Assessments } from "./pages/assessments/Assessments";
import { StudentSettings } from "./pages/settings/StudentSettings";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route
          path="/student/onboarding"
          element={
            <PrivateRoute>
              <OnboardingRouter />
            </PrivateRoute>
          }
        />
        <Route
          path="/student/onboarding/profile"
          element={
            <PrivateRoute>
              <ProfileQuestionnaire />
            </PrivateRoute>
          }
        />
        <Route
          path="/student/dashboard"
          element={
            <PrivateRoute>
              <ErrorBoundary role="student">
                <StudentDashboard />
              </ErrorBoundary>
            </PrivateRoute>
          }
        />
        <Route
          path="/student/my-progress"
          element={
            <PrivateRoute>
              <ErrorBoundary role="student">
                <MyProgress />
              </ErrorBoundary>
            </PrivateRoute>
          }
        />
        <Route
          path="/student/study-plans"
          element={
            <PrivateRoute>
              <ErrorBoundary role="student">
                <StudyPlans />
              </ErrorBoundary>
            </PrivateRoute>
          }
        />
        <Route
          path="/student/assessments"
          element={
            <PrivateRoute>
              <ErrorBoundary role="student">
                <Assessments />
              </ErrorBoundary>
            </PrivateRoute>
          }
        />
        <Route
          path="/student/settings"
          element={
            <PrivateRoute>
              <RoleRoute allowedRoles={[UserRole.STUDENT]}>
                <StudentSettings />
              </RoleRoute>
            </PrivateRoute>
          }
        />
        {/* Catch-all for any unmatched /student/* routes - redirect to dashboard */}
        <Route
          path="/student/*"
          element={
            <PrivateRoute>
              <ErrorBoundary role="student">
                <StudentDashboard />
              </ErrorBoundary>
            </PrivateRoute>
          }
        />
      </Routes>
    </BrowserRouter>
  );
}
