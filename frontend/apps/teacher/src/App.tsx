import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { PrivateRoute, RoleRoute, useAuth } from "@kaihle/auth";
import { LoginPage } from "./pages/LoginPage";
import { DashboardLayout } from "@kaihle/ui";
import { TeacherDashboard } from "./pages/dashboard/TeacherDashboard";
import { Link } from "react-router-dom";
import { Button } from "@kaihle/ui";
import { Plus } from "lucide-react";

function TeacherApp() {
  const { user, logout } = useAuth();

  const greeting = () => {
    const hour = new Date().getHours();
    if (hour < 12) return "Good morning";
    if (hour < 18) return "Good afternoon";
    return "Good evening";
  };

  const teacherName = user?.email?.split("@")[0] || "Teacher";

  return (
    <DashboardLayout
      variant="teacher"
      pageTitle={`${greeting()}, ${teacherName}`}
      onLogout={logout}
      topNavAction={
        <Link to="/teacher/assessments/new">
          <Button
            variant="primary"
            size="sm"
            className="gap-1 bg-brand-gold hover:bg-brand-gold-dark"
          >
            <Plus className="w-4 h-4" />
            Assessment
          </Button>
        </Link>
      }
    >
      <TeacherDashboard />
    </DashboardLayout>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route
          path="/teacher/*"
          element={
            <PrivateRoute>
              <RoleRoute
                allowedRoles={["TEACHER", "SCHOOL_ADMIN", "KAIHLE_ADMIN"]}
              >
                <TeacherApp />
              </RoleRoute>
            </PrivateRoute>
          }
        />
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
