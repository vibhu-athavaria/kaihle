import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@kaihle/auth";
import { LoginForm } from "@kaihle/ui";

export function LoginPage() {
  const { login, sendMagicLink } = useAuth();
  const navigate = useNavigate();

  const [error, setError] = useState<string | null>(null);

  const handleLogin = async (email: string, password: string) => {
    try {
      setError(null);
      await login({ email, password });
      navigate("/kaihle-admin/dashboard");
      // PasswordSetupRoute guard will intercept and redirect to setup-password
      // if the JWT has scope: "password_setup"
    } catch (err) {
      setError("Invalid email or password. Please try again.");
    }
  };

  return (
    <div>
      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-600">
          {error}
        </div>
      )}
      <LoginForm
        onLogin={handleLogin}
        onMagicLink={sendMagicLink}
        logoLabel="Kaihle Admin"
      />
    </div>
  );
}
