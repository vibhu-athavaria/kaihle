import { useSearchParams, useNavigate } from "react-router-dom";
import { ResetPasswordPage } from "@kaihle/ui";
import { apiClient } from "./apiClient";

/**
 * Drop-in route element for /reset-password.
 * Owns the router-context reads (useSearchParams, useNavigate) so that
 * ResetPasswordPage in packages/ui stays free of router hooks.
 */
export function ResetPasswordRoute() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();

  return (
    <ResetPasswordPage
      token={searchParams.get("token") ?? ""}
      onReset={(token, password) =>
        apiClient.post("/api/v1/auth/reset-password", {
          token,
          password,
          confirm_password: password,
        })
      }
      onSuccess={() =>
        navigate("/login", { replace: true, state: { passwordReset: true } })
      }
      appLoginPath="/login"
      forgotPasswordPath="/forgot-password"
    />
  );
}
