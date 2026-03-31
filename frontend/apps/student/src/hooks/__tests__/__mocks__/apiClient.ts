/**
 * Mock for @kaihle/auth apiClient for testing.
 */

export const apiClient = {
  get: jest.fn(),
  post: jest.fn(),
  put: jest.fn(),
  delete: jest.fn(),
  patch: jest.fn(),
};

export default apiClient;
