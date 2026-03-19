import { useNavigate } from "react-router-dom";
import { useAuth } from "@kaihle/auth";
import { LoginForm } from "@kaihle/ui";

export function LoginPage() {
  const { login, sendMagicLink } = useAuth();
  const navigate = useNavigate();

  const handleLogin = async (email: string, password: string) => {
    await login({ email, password });
    navigate("/kaihle-admin/dashboard");
    // PasswordSetupRoute guard will intercept and redirect to setup-password
    // if the JWT has scope: "password_setup"
  };

  return (
    <LoginForm
      onLogin={handleLogin}
      onMagicLink={sendMagicLink}
      logoLabel="Kaihle Admin"
    />
  );
}
