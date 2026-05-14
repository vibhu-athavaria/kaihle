import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@kaihle/auth";
import { UserRole } from "@kaihle/types";
import { LoginForm } from "@kaihle/ui";
import { useQuestionnaireStore } from "../store/questionnaireStore";

export function LoginPage() {
  const { login, logout, sendMagicLink } = useAuth();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const resetQuestionnaire = useQuestionnaireStore((s) => s.reset);
  const [error, setError] = useState<string | null>(null);

  const handleLogin = async (email: string, password: string) => {
    setError(null);
    try {
      // Clear previous user's cached server data and wizard answers before
      // setting new tokens — prevents cross-user data bleed in React Query cache.
      queryClient.clear();
      resetQuestionnaire();
      const user = await login({ email, password });
      // Validate that only students can log in through student portal
      if (user.role !== UserRole.STUDENT) {
        // Clear tokens since non-student logged in
        await logout();
        setError(
          "This login is for students only. Please use your school's teacher portal.",
        );
        return;
      }
      navigate("/student/onboarding");
    } catch {
      setError("Invalid email or password");
    }
  };

  return (
    <LoginForm
      onLogin={handleLogin}
      onMagicLink={sendMagicLink}
      logoLabel="Student Portal"
      error={error || undefined}
      forgotPasswordPath="/forgot-password"
      buttonClassName="bg-brand-primary hover:bg-brand-dark text-white"
    />
  );
}
