// src/lib/authToken.ts

const TOKEN_KEY = "token";

export const getAuthHeader = (): string | null => {
  const token = localStorage.getItem(TOKEN_KEY);
  return token ? `Bearer ${token}` : null;
};

export const setAuthToken = (token: string) => {
  localStorage.setItem(TOKEN_KEY, token);
};

export const clearAuthToken = () => {
  localStorage.removeItem(TOKEN_KEY);
};
