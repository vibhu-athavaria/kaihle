import { BrowserRouter, Routes, Route } from "react-router-dom";
import { PrivateRoute, RoleRoute } from "@kaihle/auth";
import { UserRole } from "@kaihle/types";
import { ErrorBoundary } from "@kaihle/ui";
import { LoginPage } from "./pages/LoginPage";
import { OnboardingRouter } from "./pages/onboarding/OnboardingRouter";
import { ProfileQuestionnaire } from "./pages/onboarding/ProfileQuestionnaire";
import { StudentDashboard } from "./pages/dashboard/StudentDashboard";
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
          path="/student/settings"
          element={
            <PrivateRoute>
              <RoleRoute allowedRoles={[UserRole.STUDENT]}>
                <StudentSettings />
              </RoleRoute>
            </PrivateRoute>
          }
        />
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
