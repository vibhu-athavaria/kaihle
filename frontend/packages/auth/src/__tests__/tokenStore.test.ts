import { useAuthStore, User } from "../tokenStore";

describe("tokenStore", () => {
  beforeEach(() => {
    // Reset the store before each test
    useAuthStore.getState().clearTokens();
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
});
