import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import { Header } from './components/Layout/Header';
import { Footer } from './components/Layout/Footer';
import { ProtectedRoute } from './components/ProtectedRoute';
import { Home } from './pages/Home';
import { SignUp } from './pages/SignUp';
import { ParentLogin } from './pages/ParentLogin';
import { StudentLogin } from './pages/StudentLogin';
import { AddChild } from './pages/AddChild';
import { Dashboard } from './pages/Dashboard';
import { ChildDashboard } from './pages/ChildDashboard';
import { AITutor } from './pages/AITutor';
import { Lesson } from './pages/Lesson';
import { StudyPlan } from './pages/StudyPlan';
import { StudentProgress } from './pages/StudentProgress';
import AssessmentPage from './pages/AssessmentPage';


const AppContent: React.FC = () => {
  const { user } = useAuth();

  // ✅ Decide where to redirect based on role
  const getDefaultDashboard = () => {
    if (!user) return '/';
    return user.role === 'parent' ? '/dashboard' : '/child-dashboard';
  };

  return (
    <div className="min-h-screen flex flex-col bg-blue-50">
      <Header variant={user ? 'dashboard' : 'landing'} />
      <main className="flex-1">
        <Routes>
          {/* Public Routes */}
          <Route path="/" element={user ? <Navigate to={getDefaultDashboard()} /> : <Home />} />
          <Route path="/signup" element={user ? <Navigate to={getDefaultDashboard()} /> : <SignUp />} />
          <Route path="/parent-login" element={user ? <Navigate to={getDefaultDashboard()} /> : <ParentLogin />} />
          <Route path="/student-login" element={user ? <Navigate to={getDefaultDashboard()} /> : <StudentLogin />} />

          {/* Parent-only Routes */}
          <Route
            path="/add-child"
            element={
              <ProtectedRoute>
                {user?.role === 'parent' ? <AddChild /> : <Navigate to="/child-dashboard" />}
              </ProtectedRoute>
            }
          />
          <Route
            path="/dashboard"
            element={
              <ProtectedRoute>
                {user?.role === 'parent' ? <Dashboard /> : <Navigate to="/child-dashboard" />}
              </ProtectedRoute>
            }
          />

          {/* Student-only Routes */}
          <Route
            path="/child-dashboard"
            element={
              <ProtectedRoute>
                {user?.role === 'student' ? <ChildDashboard /> : <Navigate to="/dashboard" />}
              </ProtectedRoute>
            }
          />
          <Route
            path="/take-assessment"
            element={
              <ProtectedRoute>
                {user?.role === 'student' ? <AssessmentPage /> : <Navigate to="/dashboard" />}
              </ProtectedRoute>
            }
          />
          <Route
            path="/ai-tutor"
            element={
              <ProtectedRoute>
                {user?.role === 'student' ? <AITutor /> : <Navigate to="/dashboard" />}
              </ProtectedRoute>
            }
          />
          <Route
            path="/lesson/:lessonId"
            element={
              <ProtectedRoute>
                {user?.role === 'student' ? <Lesson /> : <Navigate to="/dashboard" />}
              </ProtectedRoute>
            }
          />
          <Route
            path="/study-plan"
            element={
              <ProtectedRoute>
                {user?.role === 'student' ? <StudyPlan /> : <Navigate to="/dashboard" />}
              </ProtectedRoute>
            }
          />
          <Route
            path="/progress"
            element={
              <ProtectedRoute>
                {user?.role === 'student' ? <StudentProgress /> : <Navigate to="/dashboard" />}
              </ProtectedRoute>
            }
          />

          {/* Static Pages */}
          <Route
            path="/about"
            element={
              <div className="min-h-screen bg-blue-50 flex items-center justify-center">
                <div className="text-center">
                  <h1 className="text-2xl font-bold text-gray-900 mb-4">About Us</h1>
                  <p className="text-gray-600">Coming soon!</p>
                </div>
              </div>
            }
          />
          <Route
            path="/contact"
            element={
              <div className="min-h-screen bg-blue-50 flex items-center justify-center">
                <div className="text-center">
                  <h1 className="text-2xl font-bold text-gray-900 mb-4">Contact</h1>
                  <p className="text-gray-600">Coming soon!</p>
                </div>
              </div>
            }
          />
        </Routes>
      </main>
      <Footer />
    </div>
  );
};

function App() {
  return (
    <AuthProvider>
      <Router>
        <AppContent />
      </Router>
    </AuthProvider>
  );
}

export default App;
