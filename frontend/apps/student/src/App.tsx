import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { PrivateRoute, OnboardingRoute } from "@kaihle/auth";
import { LoginPage } from "./pages/LoginPage";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route
          path="/student/onboarding"
          element={
            <PrivateRoute>
              {/* Onboarding page — implemented in M0-6-T4 */}
              <div className="p-8 text-gray-500">
                Student onboarding — coming in M0-6-T4
              </div>
            </PrivateRoute>
          }
        />
        <Route
          path="/student/*"
          element={
            <PrivateRoute>
              <OnboardingRoute>
                {/* Student dashboard — implemented in later milestones */}
                <div className="p-8 text-gray-500">
                  Student dashboard — coming in M2
                </div>
              </OnboardingRoute>
            </PrivateRoute>
          }
        />
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
