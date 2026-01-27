module.exports = {
  testEnvironment: 'node',
  testMatch: ['**/tests/**/*.test.js'],
  collectCoverageFrom: [
    'index.html',
    'styles.css'
  ],
  coveragePathIgnorePatterns: [
    '/node_modules/',
    '/images/'
  ],
  verbose: true,
  testTimeout: 30000
};
