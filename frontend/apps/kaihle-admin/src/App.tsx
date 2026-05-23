import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import {
  PrivateRoute,
  RoleRoute,
  PasswordSetupRoute,
  ResetPasswordRoute,
  ForgotPasswordRoute,
} from "@kaihle/auth";
import { ErrorBoundary } from "@kaihle/ui";
import { LoginPage } from "./pages/LoginPage";
import { PasswordSetupPage } from "./pages/PasswordSetupPage";
import { AdminOverview } from "./pages/AdminOverview";
import { AdminCurriculum } from "./pages/AdminCurriculum";
import { AdminBilling } from "./pages/AdminBilling";
import { AdminLogs } from "./pages/AdminLogs";
import { AdminSchools } from "./pages/AdminSchools";
import { AdminSchoolDetail } from "./pages/AdminSchoolDetail";
import { AdminConfig } from "./pages/AdminConfig";
import { AdminUsers } from "./pages/AdminUsers";
import { AdminGrades } from "./pages/AdminGrades";
import { AdminQuestionReview } from "./pages/AdminQuestionReview";
import { ContentReviewQueue } from "./pages/content/VideoReviewQueue";
import { ContentReviewDetail } from "./pages/content/VideoReviewDetail";
import { ScriptsPage } from "./pages/scripts/ScriptsPage";
import { ScriptDetailPage } from "./pages/scripts/ScriptDetailPage";
import { SmokeTestPage } from "./pages/scripts/SmokeTestPage";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/forgot-password" element={<ForgotPasswordRoute />} />
        <Route path="/reset-password" element={<ResetPasswordRoute />} />
        <Route
          path="/kaihle-admin/setup-password"
          element={
            <PrivateRoute>
              <PasswordSetupPage />
            </PrivateRoute>
          }
        />
        <Route
          path="/kaihle-admin/*"
          element={
            <PrivateRoute>
              <PasswordSetupRoute>
                <RoleRoute allowedRoles={["KAIHLE_ADMIN"]}>
                  <ErrorBoundary role="kaihle-admin">
                    <Routes>
                      <Route path="dashboard" element={<AdminOverview />} />
                      <Route path="billing" element={<AdminBilling />} />
                      <Route path="logs" element={<AdminLogs />} />
                      <Route path="schools" element={<AdminSchools />} />
                      <Route
                        path="schools/:schoolId"
                        element={<AdminSchoolDetail />}
                      />
                      <Route path="config" element={<AdminConfig />} />
                      <Route path="users" element={<AdminUsers />} />
                      <Route path="curriculum" element={<AdminCurriculum />} />
                      <Route path="grades" element={<AdminGrades />} />
                      <Route
                        path="question-bank"
                        element={<AdminQuestionReview />}
                      />
                      <Route
                        path="content/review"
                        element={<ContentReviewQueue />}
                      />
                      <Route
                        path="content/review/:subtopicId"
                        element={<ContentReviewDetail />}
                      />
                      {/* Legacy redirect */}
                      <Route
                        path="content/videos"
                        element={<ContentReviewQueue />}
                      />
                      <Route
                        path="content/videos/:subtopicId"
                        element={<ContentReviewDetail />}
                      />
                      <Route path="scripts" element={<ScriptsPage />} />
                      <Route
                        path="scripts/:scriptName"
                        element={<ScriptDetailPage />}
                      />
                      <Route
                        path="scripts/smoke-tests/:testName"
                        element={<SmokeTestPage />}
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
