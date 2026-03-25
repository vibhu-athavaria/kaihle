import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { PrivateRoute } from "@kaihle/auth";
import { ErrorBoundary } from "@kaihle/ui";
import { LoginPage } from "./pages/LoginPage";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route
          path="/parent/*"
          element={
            <PrivateRoute>
              <ErrorBoundary role="parent">
                {/* Parent routes — implemented in later milestones */}
                <div className="p-8 text-gray-500">
                  Parent dashboard — coming in M5
                </div>
              </ErrorBoundary>
            </PrivateRoute>
          }
        />
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
