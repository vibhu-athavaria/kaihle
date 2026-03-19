import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { PrivateRoute, OnboardingRoute } from "@kaihle/auth";
import { LoginPage } from "./pages/LoginPage";
import { OnboardingRouter } from "./pages/onboarding/OnboardingRouter";
import { ProfileQuestionnaire } from "./pages/onboarding/ProfileQuestionnaire";
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
          path="/student/*"
          element={
            <PrivateRoute>
              <OnboardingRoute>
                <StudentDashboard />
              </OnboardingRoute>
            </PrivateRoute>
          }
        />
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
