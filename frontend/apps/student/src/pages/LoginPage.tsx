import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@kaihle/auth";
import { UserRole } from "@kaihle/types";
import { LoginForm } from "@kaihle/ui";

export function LoginPage() {
  const { login, logout, sendMagicLink } = useAuth();
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);

  const handleLogin = async (email: string, password: string) => {
    setError(null);
    try {
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
      buttonClassName="bg-brand-primary hover:bg-brand-dark text-white"
    />
  );
}
