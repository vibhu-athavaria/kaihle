import React from "react";
import { BrowserRouter as Router, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider, useAuth } from "./contexts/AuthContext";

import { Header } from "./components/Layout/Header";
import { Footer } from "./components/Layout/Footer";
import { ProtectedRoute } from "./components/ProtectedRoute";
import { TrialStatusNotice } from "./components/TrialStatusNotice";

import { Home } from "./pages/Home";
import { SignUp } from "./pages/SignUp";
import { ParentLogin } from "./pages/ParentLogin";
import { StudentLogin } from "./pages/StudentLogin";

import { Dashboard } from "./pages/Dashboard";
import { ParentSettings } from "./pages/ParentSettings";
import { PlanSelection } from "./pages/PlanSelection";
import { PaymentPage } from "./pages/PaymentPage";
import { PaymentSuccess } from "./pages/PaymentSuccess";
import { AddChild } from "./pages/AddChild";
import { EditChild } from "./pages/EditChild";

import { ChildDashboard } from "./pages/ChildDashboard";
import  CompleteProfile  from "./pages/CompleteProfile";
import { AITutor } from "./pages/AITutor";
import { Lesson } from "./pages/Lesson";
import { StudyPlan } from "./pages/StudyPlan";
import { StudentProgress } from "./pages/StudentProgress";
import AssessmentPage from "./pages/AssessmentPage";
import AssessmentDiagnosticSummary from "./pages/AssessmentDiagnosticSummary";
import CoursePage from "./pages/CoursePage";

/* -------------------------------------------------- */
/* App Shell */
/* -------------------------------------------------- */

const AppContent: React.FC = () => {
  const { user } = useAuth();

  const defaultRedirect =
    user?.role === "parent"
      ? "/dashboard"
      : user?.role === "student"
      ? "/child-dashboard"
      : "/";

  return (
    <div className="min-h-screen flex flex-col bg-blue-50">
      <Header variant={user ? "dashboard" : "landing"} />
      <TrialStatusNotice />

      <main className="flex-1">
        <Routes>
          {/* ---------------- PUBLIC ---------------- */}
          <Route path="/" element={user ? <Navigate to={defaultRedirect} /> : <Home />} />
          <Route path="/signup" element={user ? <Navigate to={defaultRedirect} /> : <SignUp />} />

          <Route
            path="/parent-login"
            element={!user ? <ParentLogin /> : <Navigate to={defaultRedirect} />}
          />
          <Route
            path="/student-login"
            element={!user ? <StudentLogin /> : <Navigate to={defaultRedirect} />}
          />

          {/* ---------------- PARENT ---------------- */}
          <Route
            path="/dashboard"
            element={
              <ProtectedRoute role="parent">
                <Dashboard />
              </ProtectedRoute>
            }
          />

          <Route
            path="/add-child"
            element={
              <ProtectedRoute role="parent">
                <AddChild />
              </ProtectedRoute>
            }
          />

          <Route
            path="/edit-child/:id"
            element={
              <ProtectedRoute role="parent">
                <EditChild />
              </ProtectedRoute>
            }
          />

          <Route
            path="/parent-settings"
            element={
              <ProtectedRoute role="parent">
                <ParentSettings />
              </ProtectedRoute>
            }
          />

          <Route
            path="/plans"
            element={
              <ProtectedRoute role="parent">
                <PlanSelection />
              </ProtectedRoute>
            }
          />

          <Route
            path="/payment"
            element={
              <ProtectedRoute role="parent">
                <PaymentPage />
              </ProtectedRoute>
            }
          />

          <Route
            path="/payment-success"
            element={
              <ProtectedRoute role="parent">
                <PaymentSuccess />
              </ProtectedRoute>
            }
          />

          {/* ---------------- STUDENT & PARENT (for profile completion) ---------------- */}
          <Route
            path="/complete-profile"
            element={
              <ProtectedRoute role={["student", "parent"]}>
                <CompleteProfile />
              </ProtectedRoute>
            }
          />

          <Route
            path="/child-dashboard"
            element={
              <ProtectedRoute role="student">
                <ChildDashboard />
              </ProtectedRoute>
            }
          />

          <Route
            path="/child-dashboard/assessment"
            element={
              <ProtectedRoute role="student">
                <AssessmentPage />
              </ProtectedRoute>
            }
          />

          <Route
            path="/child-dashboard/assessment-diagnostic-report"
            element={
              <ProtectedRoute role="student">
                <AssessmentDiagnosticSummary />
              </ProtectedRoute>
            }
          />

          <Route
            path="/ai-tutor"
            element={
              <ProtectedRoute role="student">
                <AITutor />
              </ProtectedRoute>
            }
          />

          <Route
            path="/lesson/:lessonId"
            element={
              <ProtectedRoute role="student">
                <Lesson />
              </ProtectedRoute>
            }
          />

          <Route
            path="/study-plan"
            element={
              <ProtectedRoute role="student">
                <StudyPlan />
              </ProtectedRoute>
            }
          />

          <Route
            path="/progress"
            element={
              <ProtectedRoute role="student">
                <StudentProgress />
              </ProtectedRoute>
            }
          />

          <Route
            path="/child-dashboard/take-micro-course"
            element={
              <ProtectedRoute role="student">
                <CoursePage
                title="Understanding Area and Perimeter"
            subtopic="Geometry Basics"
            videoUrl="https://www.youtube.com/embed/dQw4w9WgXcQ"
            textContent={`Area and perimeter are two fundamental concepts in geometry that help us measure shapes.

**Perimeter** is the distance around the outside of a shape. To find the perimeter, you add up the lengths of all the sides.

For example, if you have a rectangle with length 5 cm and width 3 cm:
Perimeter = 5 + 3 + 5 + 3 = 16 cm

**Area** is the amount of space inside a shape. For rectangles, you multiply the length by the width.

Using the same rectangle:
Area = 5 × 3 = 15 cm²

Remember: Perimeter is measured in units (cm, m, etc.) while area is measured in square units (cm², m², etc.).`}
            learningObjectives={[
              "Understand the difference between area and perimeter",
              "Calculate the perimeter of rectangles and squares",
              "Calculate the area of rectangles and squares",
              "Apply formulas to solve real-world problems",
            ]}
            outcomes={[
              "Confidently measure the perimeter of any rectangular shape",
              "Calculate area using the correct formula",
              "Recognize when to use area vs perimeter in real situations",
            ]}
            guidedProblems={[
              "A rectangular garden is 8 meters long and 5 meters wide. What is its perimeter?",
              "If the same garden needs to be covered with grass, what is the area that needs grass?",
              "A square room has sides of 4 meters. Find both the perimeter and area.",
              "A rectangular field is 12 feet long and 7 feet wide. Calculate the perimeter.",
              "What is the area of a rectangle with length 9 cm and width 6 cm?",
            ]}
            quiz={[
              {
                question:
                  "What is the perimeter of a rectangle with length 6 cm and width 4 cm?",
                options: ["10 cm", "20 cm", "24 cm", "40 cm"],
                answer: "20 cm",
              },
              {
                question:
                  "What is the area of a square with sides of 5 meters?",
                options: ["20 m²", "25 m²", "10 m²", "50 m²"],
                answer: "25 m²",
              },
              {
                question:
                  "If you want to put a fence around a garden, are you measuring area or perimeter?",
                options: [
                  "Area",
                  "Perimeter",
                  "Both",
                  "Neither",
                ],
                answer: "Perimeter",
              },
              {
                question:
                  "What is the area of a rectangle with length 8 cm and width 3 cm?",
                options: [
                  "11 cm²",
                  "22 cm²",
                  "24 cm²",
                  "64 cm²",
                ],
                answer: "24 cm²",
              },
            ]}
            />
              </ProtectedRoute>
            }
          />

          {/* ---------------- SYSTEM ---------------- */}
          <Route
            path="/unauthorized"
            element={
              <div className="min-h-screen flex items-center justify-center">
                <h1 className="text-xl font-semibold text-red-600">
                  You are not authorized to access this page.
                </h1>
              </div>
            }
          />

          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>

      <Footer />
    </div>
  );
};

/* -------------------------------------------------- */
/* Root */
/* -------------------------------------------------- */

export default function App() {
  return (
    <AuthProvider>
      <Router>
        <AppContent />
      </Router>
    </AuthProvider>
  );
}
