import { ForgotPasswordPage } from "@kaihle/ui";
import { apiClient } from "./apiClient";

/**
 * Drop-in route element for /forgot-password.
 * Centralizes the API call so App.tsx stays free of auth business logic.
 */
export function ForgotPasswordRoute({
  appLoginPath = "/login",
}: {
  appLoginPath?: string;
}) {
  return (
    <ForgotPasswordPage
      onSubmit={(email) =>
        apiClient.post("/api/v1/auth/forgot-password", { email })
      }
      appLoginPath={appLoginPath}
    />
  );
}
