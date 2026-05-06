import {
  BrowserRouter,
  Routes,
  Route,
  Navigate,
  useSearchParams,
  useNavigate,
} from "react-router-dom";
import {
  PrivateRoute,
  RoleRoute,
  PasswordSetupRoute,
  apiClient,
} from "@kaihle/auth";
import {
  ErrorBoundary,
  ForgotPasswordPage,
  ResetPasswordPage,
} from "@kaihle/ui";
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
import { VideoReviewQueue } from "./pages/content/VideoReviewQueue";
import { VideoReviewDetail } from "./pages/content/VideoReviewDetail";

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
                        path="content/videos"
                        element={<VideoReviewQueue />}
                      />
                      <Route
                        path="content/videos/:subtopicId"
                        element={<VideoReviewDetail />}
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
