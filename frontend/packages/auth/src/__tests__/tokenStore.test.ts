import { useAuthStore, User } from "../tokenStore";

const STORAGE_KEY = "kaihle-auth";

describe("tokenStore", () => {
  beforeEach(() => {
    useAuthStore.getState().clearTokens();
    localStorage.clear();
  });

  afterEach(() => {
    localStorage.clear();
  });

  test("setTokens stores tokens and sets isAuthenticated true", () => {
    const mockUser: User = {
      id: "user-123",
      email: "test@example.com",
      role: "STUDENT",
      school_id: "school-456",
    };

    useAuthStore
      .getState()
      .setTokens("access-token-123", "refresh-token-456", mockUser);

    const state = useAuthStore.getState();
    expect(state.accessToken).toBe("access-token-123");
    expect(state.refreshToken).toBe("refresh-token-456");
    expect(state.user).toEqual(mockUser);
    expect(state.isAuthenticated).toBe(true);
  });

  test("clearTokens resets all state", () => {
    const mockUser: User = {
      id: "user-123",
      email: "test@example.com",
      role: "STUDENT",
      school_id: "school-456",
    };

    // First set some tokens
    useAuthStore
      .getState()
      .setTokens("access-token-123", "refresh-token-456", mockUser);

    // Then clear them
    useAuthStore.getState().clearTokens();

    const state = useAuthStore.getState();
    expect(state.accessToken).toBeNull();
    expect(state.refreshToken).toBeNull();
    expect(state.user).toBeNull();
    expect(state.isAuthenticated).toBe(false);
  });

  test("updateAccessToken replaces access token without clearing refresh", () => {
    const mockUser: User = {
      id: "user-123",
      email: "test@example.com",
      role: "STUDENT",
      school_id: "school-456",
    };

    // Set initial tokens
    useAuthStore
      .getState()
      .setTokens("old-access-token", "refresh-token-456", mockUser);

    // Update only access token
    useAuthStore.getState().updateAccessToken("new-access-token");

    const state = useAuthStore.getState();
    expect(state.accessToken).toBe("new-access-token");
    expect(state.refreshToken).toBe("refresh-token-456");
    expect(state.user).toEqual(mockUser);
    expect(state.isAuthenticated).toBe(true);
  });

  describe("localStorage persistence", () => {
    const mockUser: User = {
      id: "user-123",
      email: "test@example.com",
      role: "STUDENT",
      school_id: "school-456",
    };

    test("AUTH-1: setTokens stores tokens in localStorage", () => {
      useAuthStore
        .getState()
        .setTokens("access-token-123", "refresh-token-456", mockUser);

      const stored = localStorage.getItem(STORAGE_KEY);
      expect(stored).not.toBeNull();
      const parsed = JSON.parse(stored!);
      expect(parsed.state.accessToken).toBe("access-token-123");
      expect(parsed.state.refreshToken).toBe("refresh-token-456");
      expect(parsed.state.user).toEqual(mockUser);
    });

    test("AUTH-2: store loads tokens from localStorage on initialization", () => {
      useAuthStore
        .getState()
        .setTokens("stored-access-token", "stored-refresh-token", mockUser);

      const state = useAuthStore.getState();
      expect(state.accessToken).toBe("stored-access-token");
      expect(state.refreshToken).toBe("stored-refresh-token");
      expect(state.user).toEqual(mockUser);
      expect(state.isAuthenticated).toBe(true);

      const stored = localStorage.getItem(STORAGE_KEY);
      expect(stored).not.toBeNull();
      const parsed = JSON.parse(stored!);
      expect(parsed.state.accessToken).toBe("stored-access-token");
      expect(parsed.state.isAuthenticated).toBe(true);
    });

    test("AUTH-3: clearTokens removes tokens from localStorage", () => {
      useAuthStore
        .getState()
        .setTokens("access-token-123", "refresh-token-456", mockUser);

      expect(localStorage.getItem(STORAGE_KEY)).not.toBeNull();

      useAuthStore.getState().clearTokens();

      const stored = localStorage.getItem(STORAGE_KEY);
      expect(stored).not.toBeNull();
      const parsed = JSON.parse(stored!);
      expect(parsed.state.accessToken).toBeNull();
      expect(parsed.state.refreshToken).toBeNull();
      expect(parsed.state.user).toBeNull();
      expect(parsed.state.isAuthenticated).toBe(false);
    });

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

      const stored = localStorage.getItem(STORAGE_KEY);
      const parsed = JSON.parse(stored!);
      expect(parsed.state.accessToken).toBeNull();
      expect(parsed.state.isAuthenticated).toBe(false);
    });
  });
});
