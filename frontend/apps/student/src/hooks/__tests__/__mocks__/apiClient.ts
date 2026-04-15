/**
 * Mock for @kaihle/auth apiClient and useAuth for testing.
 */

export const apiClient = {
  get: jest.fn(),
  post: jest.fn(),
  put: jest.fn(),
  delete: jest.fn(),
  patch: jest.fn(),
};

export const useAuth = jest.fn(() => ({
  user: { id: "test-user-id", role: "STUDENT" },
  logout: jest.fn(),
}));

export default apiClient;
