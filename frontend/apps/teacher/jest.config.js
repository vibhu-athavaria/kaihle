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
    '^@kaihle/types$': '<rootDir>/../../packages/types/src/index.ts',
    '^@kaihle/auth$': '<rootDir>/src/tests/__mocks__/kaihle-auth.ts',
    '^@kaihle/ui$': '<rootDir>/src/tests/__mocks__/kaihle-ui.ts',
  },
  transform: {
    '^.+\\.tsx?$': ['ts-jest', {
      tsconfig: {
        jsx: 'react-jsx',
        esModuleInterop: true,
        module: 'ESNext',
        moduleResolution: 'bundler',
        types: ['jest', '@testing-library/jest-dom'],
        // Relax strictness for test files — production code uses noUnusedLocals via tsconfig.json
        noUnusedLocals: false,
        noUnusedParameters: false,
      },
    }],
  },
  passWithNoTests: true,
};
