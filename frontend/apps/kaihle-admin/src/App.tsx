import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { PrivateRoute, RoleRoute, PasswordSetupRoute } from "@kaihle/auth";
import { ErrorBoundary } from "@kaihle/ui";
import { LoginPage } from "./pages/LoginPage";
import { PasswordSetupPage } from "./pages/PasswordSetupPage";
import { AdminOverview } from "./pages/AdminOverview";
import { AdminBilling } from "./pages/AdminBilling";
import { AdminLogs } from "./pages/AdminLogs";
import { AdminSchools } from "./pages/AdminSchools";
import { AdminSchoolDetail } from "./pages/AdminSchoolDetail";
import { AdminConfig } from "./pages/AdminConfig";
import { AdminUsers } from "./pages/AdminUsers";
import { AdminQuestionReview } from "./pages/AdminQuestionReview";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route
          path="/kaihle-admin/setup-password"
          element={
            <PrivateRoute>
              <PasswordSetupPage />
            </PrivateRoute>
          }
        />
        <Route
          path="/kaihle-admin/*"
          element={
            <PrivateRoute>
              <PasswordSetupRoute>
                <RoleRoute allowedRoles={["KAIHLE_ADMIN"]}>
                  <ErrorBoundary role="kaihle-admin">
                    <Routes>
                      <Route path="dashboard" element={<AdminOverview />} />
                      <Route path="billing" element={<AdminBilling />} />
                      <Route path="logs" element={<AdminLogs />} />
                      <Route path="schools" element={<AdminSchools />} />
                      <Route
                        path="schools/:schoolId"
                        element={<AdminSchoolDetail />}
                      />
                      <Route path="config" element={<AdminConfig />} />
                      <Route path="users" element={<AdminUsers />} />
                      <Route
                        path="question-bank"
                        element={<AdminQuestionReview />}
                      />
                      <Route
                        index
                        element={<Navigate to="dashboard" replace />}
                      />
                    </Routes>
                  </ErrorBoundary>
                </RoleRoute>
              </PasswordSetupRoute>
            </PrivateRoute>
          }
        />
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
