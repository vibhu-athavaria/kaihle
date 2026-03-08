import { create } from "zustand";

export interface User {
  id: string;
  email: string;
  role: "STUDENT" | "TEACHER" | "SCHOOL_ADMIN" | "PARENT" | "KAIHLE_ADMIN";
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

export const useAuthStore = create<AuthState>((set) => ({
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
}));
