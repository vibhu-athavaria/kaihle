import {
  BrowserRouter,
  Routes,
  Route,
  Navigate,
  useSearchParams,
  useNavigate,
} from "react-router-dom";
import { PrivateRoute, RoleRoute, useAuthStore, apiClient } from "@kaihle/auth";
import {
  ParentLayout,
  ForgotPasswordPage,
  ResetPasswordPage,
} from "@kaihle/ui";
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

function ResetPasswordRoute() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  return (
    <ResetPasswordPage
      token={searchParams.get("token") ?? ""}
      onReset={(token, password) =>
        apiClient.post("/api/v1/auth/reset-password", {
          token,
          password,
          confirm_password: password,
        })
      }
      onSuccess={() => navigate("/login", { replace: true })}
      appLoginPath="/login"
      forgotPasswordPath="/forgot-password"
    />
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route
          path="/forgot-password"
          element={
            <ForgotPasswordPage
              onSubmit={(email) =>
                apiClient.post("/api/v1/auth/forgot-password", { email })
              }
              appLoginPath="/login"
            />
          }
        />
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
