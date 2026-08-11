import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";
import { type UserRole as UserRoleType } from "@kaihle/types";

const STORAGE_KEY = "kaihle-auth";

export interface User {
  id: string;
  email: string;
  username: string;
  first_name: string;
  role: UserRoleType;
  school_id: string | null;
  permissions: Record<string, boolean> | null;
}

/** The Kaihle Admin acting as this user, when the session was started via impersonation. */
export interface Impersonator {
  id: string;
  name: string;
}

export interface LoginResponse {
  access_token: string;
  /** null for impersonated sessions — those are deliberately not refreshable. */
  refresh_token: string | null;
  token_type: string;
  must_change_password: boolean;
  user: User;
  impersonator?: Impersonator | null;
}

export interface AuthState {
  accessToken: string | null;
  refreshToken: string | null;
  user: User | null;
  isAuthenticated: boolean;
  mustChangePassword: boolean;
  impersonator: Impersonator | null;
  setTokens: (
    access: string,
    refresh: string | null,
    user: User,
    mustChangePassword?: boolean,
    impersonator?: Impersonator | null,
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
      impersonator: null,

      setTokens: (
        access,
        refresh,
        user,
        mustChangePassword = false,
        impersonator = null,
      ) =>
        set({
          accessToken: access,
          refreshToken: refresh,
          user,
          isAuthenticated: true,
          mustChangePassword,
          impersonator,
        }),

      clearTokens: () =>
        set({
          accessToken: null,
          refreshToken: null,
          user: null,
          isAuthenticated: false,
          mustChangePassword: false,
          impersonator: null,
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
        impersonator: state.impersonator,
      }),
    },
  ),
);
