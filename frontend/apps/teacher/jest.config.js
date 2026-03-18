export default {
  testPathIgnorePatterns: ['/node_modules/', '/src/tests/'],
  transform: {
    '^.+\\.tsx?$': ['ts-jest', { useESN: true }],
  },
  moduleNameMapper: {
    '^@/(.*)$': '<rootDir>/src/$1',
  },
};
