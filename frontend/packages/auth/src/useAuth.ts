import { useCallback } from "react";
import { useAuthStore } from "./tokenStore";
import { apiClient } from "./apiClient";

interface LoginCredentials {
  email: string;
  password: string;
}

export function useAuth() {
  const { user, isAuthenticated, setTokens, clearTokens } = useAuthStore();

  const login = useCallback(
    async (credentials: LoginCredentials) => {
      const response = await apiClient.post("/api/v1/auth/login", credentials);
      const { access_token, refresh_token, user: userData } = response.data;
      setTokens(access_token, refresh_token, userData);
      return userData;
    },
    [setTokens],
  );

  const logout = useCallback(async () => {
    const { refreshToken } = useAuthStore.getState();
    if (refreshToken) {
      try {
        await apiClient.post("/api/v1/auth/logout", {
          refresh_token: refreshToken,
        });
      } catch {
        // Ignore errors on logout
      }
    }
    clearTokens();
  }, [clearTokens]);

  const sendMagicLink = useCallback(async (email: string) => {
    await apiClient.post("/api/v1/auth/magic-link", { email });
  }, []);

  return { user, isAuthenticated, login, logout, sendMagicLink };
}
