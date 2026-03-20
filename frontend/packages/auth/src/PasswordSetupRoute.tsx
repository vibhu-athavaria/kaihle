import { useMemo } from "react";
import { Navigate } from "react-router-dom";
import { jwtDecode } from "jwt-decode";
import { useAuthStore } from "./tokenStore";
import { UserRole } from "@kaihle/types";

/**
 * Maps UserRole to the URL path prefix for that role.
 */
function roleToPathPrefix(role: UserRole): string {
  switch (role) {
    case UserRole.STUDENT:
      return "student";
    case UserRole.TEACHER:
      return "teacher";
    case UserRole.SCHOOL_ADMIN:
      return "school-admin";
    case UserRole.PARENT:
      return "parent";
    case UserRole.KAIHLE_ADMIN:
      return "kaihle-admin";
    default:
      return "";
  }
}

interface JWTPayload {
  sub?: string;
  scope?: string;
  exp?: number;
  iat?: number;
  type?: string;
}

/**
 * Route guard that intercepts a scoped password_setup JWT and redirects
 * to the password setup screen before allowing access to protected routes.
 *
 * How it works:
 * 1. Reads the access token from the Zustand tokenStore
 * 2. Decodes the JWT (client-side, no verification — verification is server-side)
 * 3. If payload.scope === "password_setup" → redirect to /{rolePrefix}/setup-password
 * 4. Otherwise → render children normally
 */
export function PasswordSetupRoute({
  children,
}: {
  children: React.ReactNode;
}) {
  const accessToken = useAuthStore((s) => s.accessToken);
  const user = useAuthStore((s) => s.user);

  const needsPasswordSetup = useMemo(() => {
    if (!accessToken) return false;
    try {
      const payload = jwtDecode<JWTPayload>(accessToken);
      return payload.scope === "password_setup";
    } catch {
      return false;
    }
  }, [accessToken]);

  if (needsPasswordSetup && user?.role) {
    const prefix = roleToPathPrefix(user.role);
    return <Navigate to={`/${prefix}/setup-password`} replace />;
  }

  return <>{children}</>;
}
