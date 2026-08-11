import { useEffect, useRef, useState } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import { apiClient } from "./apiClient";
import { useAuthStore, type LoginResponse } from "./tokenStore";

export interface ImpersonateRouteProps {
  /** Where to land after the session is established, e.g. "/student/dashboard". */
  homePath: string;
}

/**
 * Drop-in route element for /impersonate — the landing point of a Kaihle Admin
 * "log in as user" link.
 *
 * Trades the single-use handoff token in the query string for a real session.
 * The exchange happens over POST so the session token itself never appears in a
 * URL; the handoff token that does appear is single-use and expires in a minute.
 *
 * Mounted OUTSIDE the auth guards — the visitor is by definition not yet
 * authenticated in this origin when they arrive.
 */
export function ImpersonateRoute({ homePath }: ImpersonateRouteProps) {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const setTokens = useAuthStore((s) => s.setTokens);
  const [error, setError] = useState<string | null>(null);

  const token = searchParams.get("token") ?? "";
  // The token is single-use, so the exchange must fire exactly once even though
  // React 18 StrictMode double-invokes effects in development.
  const attempted = useRef(false);

  useEffect(() => {
    if (attempted.current) return;
    attempted.current = true;

    if (!token) {
      setError("This link is missing its token.");
      return;
    }

    apiClient
      .post<LoginResponse>("/api/v1/auth/impersonate/redeem", { token })
      .then(({ data }) => {
        setTokens(
          data.access_token,
          data.refresh_token,
          data.user,
          false,
          data.impersonator ?? null,
        );
        navigate(homePath, { replace: true });
      })
      .catch(() => {
        setError(
          "This impersonation link is invalid, expired, or has already been used. Generate a new one from the admin console.",
        );
      });
  }, [token, homePath, navigate, setTokens]);

  if (error) {
    return (
      <div className="flex min-h-screen items-center justify-center px-6">
        <div className="max-w-sm text-center">
          <div className="mb-4 text-4xl">🔒</div>
          <h1 className="mb-2 font-display text-xl font-bold text-brand-ink">
            Link no longer valid
          </h1>
          {/* No retry affordance — the token is single-use, so retrying it here
              could never succeed. */}
          <p className="font-sans text-sm text-brand-body">{error}</p>
        </div>
      </div>
    );
  }

  // A full-page spinner is the correct pattern here: this is token verification,
  // the documented exception in DESIGN_SYSTEM §10.
  return (
    <div className="flex min-h-screen items-center justify-center">
      <div
        className="h-8 w-8 animate-spin rounded-full border-2 border-brand-primary border-t-transparent"
        role="status"
        aria-label="Starting session"
      />
    </div>
  );
}
