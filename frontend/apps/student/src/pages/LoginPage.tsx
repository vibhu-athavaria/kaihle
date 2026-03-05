import { useNavigate } from "react-router-dom";
import { useAuth } from "@kaihle/auth";
import { LoginForm } from "@kaihle/ui";

export function LoginPage() {
  const { login, sendMagicLink } = useAuth();
  const navigate = useNavigate();

  const handleLogin = async (email: string, password: string) => {
    await login({ email, password });
    // After login, navigate to /student/onboarding
    // OnboardingRoute will handle redirect to dashboard if already complete
    navigate("/student/onboarding");
  };

  return (
    <LoginForm
      onLogin={handleLogin}
      onMagicLink={sendMagicLink}
      logoLabel="Student Portal"
    />
  );
}
