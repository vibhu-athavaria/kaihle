import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import {
  PrivateRoute,
  RoleRoute,
  PasswordSetupRoute,
  ResetPasswordRoute,
  ForgotPasswordRoute,
} from "@kaihle/auth";
import { ErrorBoundary } from "@kaihle/ui";
import { UserRole } from "@kaihle/types";
import { LoginPage } from "./pages/LoginPage";
import { PasswordSetupPage } from "./pages/PasswordSetupPage";
import { SchoolOverview } from "./pages/SchoolOverview";
import { UsersPage } from "./pages/UsersPage";
import { StudentDetailPage } from "./pages/StudentDetailPage";
import { TeacherDetailPage } from "./pages/TeacherDetailPage";
import { ParentDetailPage } from "./pages/ParentDetailPage";
import { ClassManagement } from "./pages/ClassManagement";
import { ClassDetailPage } from "./pages/ClassDetailPage";
import { AnalyticsPage } from "./pages/AnalyticsPage";
import { SchoolAdminSettingsPage } from "./pages/settings/SchoolAdminSettingsPage";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/forgot-password" element={<ForgotPasswordRoute />} />
        <Route path="/reset-password" element={<ResetPasswordRoute />} />

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
                      <Route path="users" element={<UsersPage />} />
                      <Route
                        path="users/students/:studentId"
                        element={<StudentDetailPage />}
                      />
                      <Route
                        path="users/teachers/:teacherId"
                        element={<TeacherDetailPage />}
                      />
                      <Route
                        path="users/parents/:parentId"
                        element={<ParentDetailPage />}
                      />
                      <Route path="classes" element={<ClassManagement />} />
                      <Route
                        path="classes/:classId"
                        element={<ClassDetailPage />}
                      />
                      <Route
                        path="settings"
                        element={<SchoolAdminSettingsPage />}
                      />
                      <Route path="analytics" element={<AnalyticsPage />} />
                      <Route
                        path="billing"
                        element={<Navigate to="dashboard" replace />}
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
