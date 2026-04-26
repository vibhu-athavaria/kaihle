import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";
import { type UserRole as UserRoleType } from "@kaihle/types";

const STORAGE_KEY = "kaihle-auth";

export interface User {
  id: string;
  email: string;
  first_name: string;
  role: UserRoleType;
  school_id: string | null;
}

export interface LoginResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  must_change_password: boolean;
  user: User;
}

export interface AuthState {
  accessToken: string | null;
  refreshToken: string | null;
  user: User | null;
  isAuthenticated: boolean;
  mustChangePassword: boolean;
  setTokens: (
    access: string,
    refresh: string,
    user: User,
    mustChangePassword?: boolean,
  ) => void;
  clearTokens: () => void;
  updateAccessToken: (access: string) => void;
  clearMustChangePassword: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      accessToken: null,
      refreshToken: null,
      user: null,
      isAuthenticated: false,
      mustChangePassword: false,

      setTokens: (access, refresh, user, mustChangePassword = false) =>
        set({
          accessToken: access,
          refreshToken: refresh,
          user,
          isAuthenticated: true,
          mustChangePassword,
        }),

      clearTokens: () =>
        set({
          accessToken: null,
          refreshToken: null,
          user: null,
          isAuthenticated: false,
          mustChangePassword: false,
        }),

      updateAccessToken: (access) => set({ accessToken: access }),

      clearMustChangePassword: () => set({ mustChangePassword: false }),
    }),
    {
      name: STORAGE_KEY,
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({
        accessToken: state.accessToken,
        refreshToken: state.refreshToken,
        user: state.user,
        isAuthenticated: state.isAuthenticated,
        mustChangePassword: state.mustChangePassword,
      }),
    },
  ),
);
