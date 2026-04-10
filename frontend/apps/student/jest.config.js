/** @type {import('jest').Config} */
export default {
  testEnvironment: 'jsdom',
  testMatch: ['**/*.test.ts', '**/*.test.tsx'],
  testPathIgnorePatterns: [
    '/node_modules/',
    '\\.spec\\.ts$', // Exclude Playwright specs
  ],
  moduleNameMapper: {
    '\\.(css|less|scss|sass)$': 'identity-obj-proxy',
    '^@kaihle/auth$': '<rootDir>/src/hooks/__tests__/__mocks__/apiClient.ts',
    '^@kaihle/types$': '<rootDir>/../../packages/types/src/index.ts',
  },
  transform: {
    '^.+\\.tsx?$': ['ts-jest', {
      tsconfig: {
        jsx: 'react-jsx',
        esModuleInterop: true,
        module: 'ESNext',
        moduleResolution: 'bundler',
        types: ['jest', 'jest-environment-jsdom'],
      },
    }],
  },
};
