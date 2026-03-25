import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { PrivateRoute, RoleRoute, PasswordSetupRoute } from "@kaihle/auth";
import { ErrorBoundary } from "@kaihle/ui";
import { UserRole } from "@kaihle/types";
import { LoginPage } from "./pages/LoginPage";
import { PasswordSetupPage } from "./pages/PasswordSetupPage";
import { SchoolOverview } from "./pages/SchoolOverview";
import { UserManagement } from "./pages/UserManagement";
import { ClassManagement } from "./pages/ClassManagement";
import { SchoolAdminSettingsPage } from "./pages/settings/SchoolAdminSettingsPage";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />

        {/* Password setup — required before any other school-admin route */}
        <Route
          path="/school-admin/setup-password"
          element={
            <PrivateRoute>
              <PasswordSetupPage />
            </PrivateRoute>
          }
        />

        {/* All school admin pages — require auth + password setup + correct role */}
        <Route
          path="/school-admin/*"
          element={
            <PrivateRoute>
              <PasswordSetupRoute>
                <RoleRoute
                  allowedRoles={[UserRole.SCHOOL_ADMIN, UserRole.KAIHLE_ADMIN]}
                >
                  <ErrorBoundary role="school-admin">
                    <Routes>
                      <Route path="dashboard" element={<SchoolOverview />} />
                      <Route path="users" element={<UserManagement />} />
                      <Route path="classes" element={<ClassManagement />} />
                      <Route
                        path="settings"
                        element={<SchoolAdminSettingsPage />}
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
