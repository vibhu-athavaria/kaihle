/** @type {import('jest').Config} */
export default {
  testEnvironment: "jsdom",
  testMatch: ["**/*.test.ts", "**/*.test.tsx"],
  testPathIgnorePatterns: [
    "/node_modules/",
    "\\.spec\\.ts$", // Exclude Playwright specs
  ],
  transform: {
    "^.+\\.(ts|tsx)$": ["ts-jest", {
      tsconfig: "tsconfig.test.json",
      diagnostics: false,
    }],
  },
  moduleNameMapper: {
    "\\.(css|less|scss|sass)$": "identity-obj-proxy",
    "^@kaihle/auth$": "<rootDir>/src/__mocks__/@kaihle/auth.ts",
    "^@kaihle/(.*)$": "<rootDir>/../../packages/$1/src/index.ts",
  },
  setupFilesAfterEnv: ["@testing-library/jest-dom"],
  passWithNoTests: true,
};
