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

export interface AuthState {
  accessToken: string | null;
  refreshToken: string | null;
  user: User | null;
  isAuthenticated: boolean;
  setTokens: (access: string, refresh: string, user: User) => void;
  clearTokens: () => void;
  updateAccessToken: (access: string) => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      accessToken: null,
      refreshToken: null,
      user: null,
      isAuthenticated: false,

      setTokens: (access, refresh, user) =>
        set({
          accessToken: access,
          refreshToken: refresh,
          user,
          isAuthenticated: true,
        }),

      clearTokens: () =>
        set({
          accessToken: null,
          refreshToken: null,
          user: null,
          isAuthenticated: false,
        }),

      updateAccessToken: (access) => set({ accessToken: access }),
    }),
    {
      name: STORAGE_KEY,
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({
        accessToken: state.accessToken,
        refreshToken: state.refreshToken,
        user: state.user,
        isAuthenticated: state.isAuthenticated,
      }),
    },
  ),
);
