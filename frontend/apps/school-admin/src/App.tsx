import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { PrivateRoute, RoleRoute } from "@kaihle/auth";
import { LoginPage } from "./pages/LoginPage";
import { SchoolOverview } from "./pages/SchoolOverview";
import { UserManagement } from "./pages/UserManagement";
import { ClassManagement } from "./pages/ClassManagement";

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
              {/* PasswordSetupPage wired in M0-9-T4 */}
              <div className="p-8 text-gray-500">
                Password setup — wired in M0-9-T4
              </div>
            </PrivateRoute>
          }
        />

        {/* All school admin pages — require auth + password setup + correct role */}
        <Route
          path="/school-admin/*"
          element={
            <PrivateRoute>
              <RoleRoute allowedRoles={["SCHOOL_ADMIN", "KAIHLE_ADMIN"]}>
                <Routes>
                  <Route path="dashboard" element={<SchoolOverview />} />
                  <Route path="users" element={<UserManagement />} />
                  <Route path="classes" element={<ClassManagement />} />
                  <Route index element={<Navigate to="dashboard" replace />} />
                </Routes>
              </RoleRoute>
            </PrivateRoute>
          }
        />

        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
