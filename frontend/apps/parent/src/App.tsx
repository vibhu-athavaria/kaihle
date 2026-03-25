import { useEffect, useState, useCallback } from "react";
import {
  BrowserRouter,
  Routes,
  Route,
  Navigate,
  useNavigate,
} from "react-router-dom";
import { PrivateRoute, RoleRoute, useAuth, apiClient } from "@kaihle/auth";
import { ParentLayout } from "@kaihle/ui";
import { LoginPage } from "./pages/LoginPage";
import { ParentSettings } from "./pages/settings/ParentSettings";

interface ParentUser {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
}

interface Child {
  id: string;
  first_name: string;
  last_name: string;
  grade: string;
  school_name: string;
}

function ParentApp() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [parentUser, setParentUser] = useState<ParentUser | null>(null);
  const [children, setChildren] = useState<Child[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!user) return;

    Promise.all([
      apiClient.get<ParentUser>("/api/v1/users/me"),
      apiClient.get<Child[]>("/api/v1/parent/children"),
    ])
      .then(([userRes, childrenRes]) => {
        setParentUser(userRes.data);
        setChildren(childrenRes.data);
      })
      .catch(() => {
        // Handle error silently
      })
      .finally(() => setLoading(false));
  }, [user]);

  const handleLogout = useCallback(() => {
    logout();
    navigate("/login");
  }, [logout, navigate]);

  if (loading) {
    return (
      <div className="min-h-screen bg-role-parent-bg flex items-center justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-gray-900" />
      </div>
    );
  }

  if (!parentUser) {
    return <Navigate to="/login" replace />;
  }

  return (
    <ParentLayout>
      <ParentSettings
        user={parentUser}
        children={children}
        onLogout={handleLogout}
      />
    </ParentLayout>
  );
}

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
                <ParentApp />
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
