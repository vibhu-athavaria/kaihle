import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { PrivateRoute } from "@kaihle/auth";
import { LoginPage } from "./pages/LoginPage";
import { DashboardLayout } from "@kaihle/ui";
import { TeacherDashboard } from "./pages/dashboard/TeacherDashboard";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route
          path="/teacher/*"
          element={
            <PrivateRoute>
              <DashboardLayout variant="teacher" pageTitle="Dashboard">
                <TeacherDashboard />
              </DashboardLayout>
            </PrivateRoute>
          }
        />
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
