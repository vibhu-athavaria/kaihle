import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { PrivateRoute, RoleRoute } from "@kaihle/auth";
import { LoginPage } from "./pages/LoginPage";
import { AdminOverview } from "./pages/AdminOverview";
import { AdminSchools } from "./pages/AdminSchools";
import { AdminSchoolDetail } from "./pages/AdminSchoolDetail";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route
          path="/kaihle-admin/setup-password"
          element={
            <PrivateRoute>
              {/* PasswordSetupPage added by M0-9-T4 */}
              <div className="p-8 text-gray-500">
                Password setup — coming in M0-9-T4
              </div>
            </PrivateRoute>
          }
        />
        <Route
          path="/kaihle-admin/*"
          element={
            <PrivateRoute>
              <RoleRoute allowedRoles={["KAIHLE_ADMIN"]}>
                <Routes>
                  <Route path="dashboard" element={<AdminOverview />} />
                  <Route path="schools" element={<AdminSchools />} />
                  <Route
                    path="schools/:schoolId"
                    element={<AdminSchoolDetail />}
                  />
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
