import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import {
  PrivateRoute,
  RoleRoute,
  ResetPasswordRoute,
  ForgotPasswordRoute,
  useAuthStore,
} from "@kaihle/auth";
import { ParentLayout } from "@kaihle/ui";
import { LoginPage } from "./pages/LoginPage";
import { ChangePasswordPage } from "./pages/ChangePasswordPage";
import { ParentSettings } from "./pages/settings/ParentSettings";

function PrivateRouteWithPasswordCheck({
  children,
}: {
  children: React.ReactNode;
}) {
  const mustChangePassword = useAuthStore((state) => state.mustChangePassword);
  return (
    <PrivateRoute>
      {mustChangePassword ? (
        <Navigate to="/parent/change-password" replace />
      ) : (
        children
      )}
    </PrivateRoute>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/forgot-password" element={<ForgotPasswordRoute />} />
        <Route path="/reset-password" element={<ResetPasswordRoute />} />
        <Route
          path="/parent/change-password"
          element={
            <PrivateRoute>
              <ChangePasswordPage />
            </PrivateRoute>
          }
        />
        <Route
          path="/parent/settings"
          element={
            <PrivateRouteWithPasswordCheck>
              <RoleRoute allowedRoles={["PARENT"]}>
                <ParentLayout>
                  <ParentSettings />
                </ParentLayout>
              </RoleRoute>
            </PrivateRouteWithPasswordCheck>
          }
        />
        <Route
          path="/parent/*"
          element={
            <PrivateRouteWithPasswordCheck>
              <RoleRoute allowedRoles={["PARENT"]}>
                <ParentLayout>
                  <div className="p-8 text-gray-500">
                    Parent dashboard — coming in M5
                  </div>
                </ParentLayout>
              </RoleRoute>
            </PrivateRouteWithPasswordCheck>
          }
        />
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
