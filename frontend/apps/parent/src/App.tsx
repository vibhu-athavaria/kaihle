import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { PrivateRoute, RoleRoute } from "@kaihle/auth";
import { ParentLayout } from "@kaihle/ui";
import { LoginPage } from "./pages/LoginPage";
import { ParentSettings } from "./pages/settings/ParentSettings";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route
          path="/parent/settings"
          element={
            <PrivateRoute>
              <RoleRoute allowedRoles={["PARENT"]}>
                <ParentLayout>
                  <ParentSettings />
                </ParentLayout>
              </RoleRoute>
            </PrivateRoute>
          }
        />
        <Route
          path="/parent/*"
          element={
            <PrivateRoute>
              <RoleRoute allowedRoles={["PARENT"]}>
                <ParentLayout>
                  <div className="p-8 text-gray-500">
                    Parent dashboard — coming in M5
                  </div>
                </ParentLayout>
              </RoleRoute>
            </PrivateRoute>
          }
        />
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
