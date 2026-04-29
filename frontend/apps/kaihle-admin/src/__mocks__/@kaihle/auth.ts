export const apiClient = {
  get: jest.fn(),
  post: jest.fn(),
  patch: jest.fn(),
  delete: jest.fn(),
};

export const useAuth = jest.fn(() => ({ logout: jest.fn(), user: null }));
export const PrivateRoute = jest.fn(
  ({ children }: { children: React.ReactNode }) => children,
);
export const RoleRoute = jest.fn(
  ({ children }: { children: React.ReactNode }) => children,
);
