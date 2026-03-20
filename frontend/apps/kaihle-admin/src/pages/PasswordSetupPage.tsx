import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@kaihle/auth";
import { PasswordSetupForm } from "@kaihle/ui";

export function PasswordSetupPage() {
  const { setPassword } = useAuth();
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (password: string) => {
    setIsLoading(true);
    setError(null);
    try {
      await setPassword(password);
      // setPassword() exchanges scoped token for full JWT in the token store
      navigate("/kaihle-admin/dashboard");
    } catch (err: unknown) {
      const message =
        err instanceof Error
          ? err.message
          : "Something went wrong. Please try again.";
      setError(message);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <PasswordSetupForm
      onSubmit={handleSubmit}
      isLoading={isLoading}
      error={error}
      logoLabel="Kaihle Admin"
    />
  );
}
