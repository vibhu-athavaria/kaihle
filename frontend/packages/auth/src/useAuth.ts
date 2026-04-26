import { useCallback } from "react";
import { useAuthStore, type LoginResponse } from "./tokenStore";
import { apiClient } from "./apiClient";

interface LoginCredentials {
  email: string;
  password: string;
}

export function useAuth() {
  const { user, isAuthenticated, setTokens, clearTokens } = useAuthStore();

  const login = useCallback(
    async (credentials: LoginCredentials) => {
      const response = await apiClient.post<LoginResponse>(
        "/api/v1/auth/login",
        credentials,
      );
      const {
        access_token,
        refresh_token,
        user: userData,
        must_change_password,
      } = response.data;
      setTokens(
        access_token,
        refresh_token,
        userData,
        must_change_password ?? false,
      );
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

  /**
   * Set password for a magic-link-invited user.
   * Posts to /api/v1/auth/set-password with the current scoped token.
   * On success, stores the returned full JWT in the tokenStore.
   * On failure, throws an error.
   */
  const setPassword = useCallback(
    async (password: string) => {
      const response = await apiClient.post<LoginResponse>(
        "/api/v1/auth/set-password",
        {
          password,
          confirm_password: password,
        },
      );
      const { access_token, refresh_token, user: userData } = response.data;
      setTokens(access_token, refresh_token, userData, false);
      return userData;
    },
    [setTokens],
  );

  return { user, isAuthenticated, login, logout, sendMagicLink, setPassword };
}
