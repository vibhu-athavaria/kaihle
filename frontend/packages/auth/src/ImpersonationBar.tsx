import { ImpersonationBanner } from "@kaihle/ui";
import { useAuthStore } from "./tokenStore";

/**
 * Container for ImpersonationBanner. Renders nothing unless the current session
 * was started by a Kaihle Admin impersonating this user.
 *
 * Mount once at the root of each target app, next to the router. Kept here
 * rather than in packages/ui so that ui takes no dependency on auth.
 */
export function ImpersonationBar() {
  const impersonator = useAuthStore((s) => s.impersonator);
  const user = useAuthStore((s) => s.user);
  const clearTokens = useAuthStore((s) => s.clearTokens);

  if (!impersonator || !user) return null;

  return (
    <ImpersonationBanner
      userName={user.first_name}
      userRole={user.role}
      impersonatorName={impersonator.name}
      onExit={() => {
        // Drop the session locally rather than calling /auth/logout: impersonated
        // sessions hold no refresh token, so there is nothing server-side to
        // revoke, and the access token expires on its own.
        clearTokens();
        window.location.replace("/login");
      }}
    />
  );
}
