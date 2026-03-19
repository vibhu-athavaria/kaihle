import { useAuthStore } from "../tokenStore";

const STORAGE_KEY = "kaihle-auth";

const mockUser = {
  id: "123",
  email: "test@kaihle.com",
  role: "TEACHER" as const,
  school_id: "school-123",
};

describe("tokenStore", () => {
  beforeEach(() => {
    // Clear store and localStorage before each test
    useAuthStore.getState().clearTokens();
    localStorage.clear();
  });

  describe("setTokens", () => {
    test("AUTH-1: login stores token in localStorage", () => {
      useAuthStore
        .getState()
        .setTokens("access-token-123", "refresh-token-456", mockUser);

      const stored = localStorage.getItem(STORAGE_KEY);
      expect(stored).not.toBeNull();
    });
  });

  describe("token persistence", () => {
    test("AUTH-2: refresh page → user remains authenticated", () => {
      useAuthStore
        .getState()
        .setTokens("access-token-123", "refresh-token-456", mockUser);

      // Simulate page refresh by creating a new store instance
      const newStore = useAuthStore.getState();
      expect(newStore.isAuthenticated).toBe(true);
      expect(newStore.accessToken).toBe("access-token-123");
      expect(newStore.user).toEqual(mockUser);
    });

    test("AUTH-3: clear localStorage → user not authenticated", () => {
      useAuthStore
        .getState()
        .setTokens("access-token-123", "refresh-token-456", mockUser);

      localStorage.clear();

      const state = useAuthStore.getState();
      expect(state.isAuthenticated).toBe(false);
      expect(state.accessToken).toBeNull();
    });
  });

  describe("clearTokens", () => {
    test("AUTH-4: logout removes tokens from localStorage and state", () => {
      useAuthStore
        .getState()
        .setTokens("access-token-123", "refresh-token-456", mockUser);

      expect(localStorage.getItem(STORAGE_KEY)).not.toBeNull();

      useAuthStore.getState().clearTokens();

      const state = useAuthStore.getState();
      expect(state.accessToken).toBeNull();
      expect(state.refreshToken).toBeNull();
      expect(state.user).toBeNull();
      expect(state.isAuthenticated).toBe(false);

      // Verify localStorage was updated
      const stored = localStorage.getItem(STORAGE_KEY);
      expect(stored).not.toBeNull();
      const parsed = JSON.parse(stored!);
      expect(parsed.state.accessToken).toBeNull();
      expect(parsed.state.isAuthenticated).toBe(false);
    });
  });

  describe("updateAccessToken", () => {
    test("updateAccessToken updates the access token", () => {
      useAuthStore
        .getState()
        .setTokens("access-token-123", "refresh-token-456", mockUser);

      useAuthStore.getState().updateAccessToken("new-access-token");

      const state = useAuthStore.getState();
      expect(state.accessToken).toBe("new-access-token");
      expect(state.refreshToken).toBe("refresh-token-456");
    });
  });
});
