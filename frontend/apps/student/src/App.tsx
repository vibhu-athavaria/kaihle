import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { PrivateRoute, RoleRoute, OnboardingRoute } from "@kaihle/auth";
import { LoginPage } from "./pages/LoginPage";
import { OnboardingRouter } from "./pages/onboarding/OnboardingRouter";
import { ProfileQuestionnaire } from "./pages/onboarding/ProfileQuestionnaire";
import { StudentLayout } from "@kaihle/ui";
import { StudentDashboard } from "./pages/dashboard/StudentDashboard";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route
          path="/student/onboarding"
          element={
            <PrivateRoute>
              <RoleRoute allowedRoles={["STUDENT"]}>
                <OnboardingRouter />
              </RoleRoute>
            </PrivateRoute>
          }
        />
        <Route
          path="/student/onboarding/profile"
          element={
            <PrivateRoute>
              <RoleRoute allowedRoles={["STUDENT"]}>
                <ProfileQuestionnaire />
              </RoleRoute>
            </PrivateRoute>
          }
        />
        <Route
          path="/student/*"
          element={
            <PrivateRoute>
              <RoleRoute allowedRoles={["STUDENT"]}>
                <OnboardingRoute>
                  <StudentLayout pageTitle="Dashboard">
                    <StudentDashboard />
                  </StudentLayout>
                </OnboardingRoute>
              </RoleRoute>
            </PrivateRoute>
          }
        />
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
