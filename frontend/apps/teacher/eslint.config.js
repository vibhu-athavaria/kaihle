// Minimal ESLint config for CI compatibility
// Note: Full ESLint setup with TypeScript should be added in M0-1-T1
export default [
  {
    files: ['**/*.js', '**/*.ts', '**/*.tsx'],
    rules: {
      'no-unused-vars': 'off',
    },
  },
];
